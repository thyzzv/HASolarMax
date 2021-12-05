import socket, re, sys

resp_ptrn = re.compile('\{..;..;..\|..:(.*)\|(....)\}')
stat_cmd_ptrn = re.compile('DD..|DM..|DY..')
elog_cmd_ptrn = re.compile('EC..')

logcodes = { '20002' : 'Irradiazione insufficiente',
             '20003' : 'Avvio',
             '20004' : 'Funzionamento su MPP',
             '20005' : 'Ventola attiva',
             '20006' : 'Regime a potenza massima',
             '20007' : 'Limitazione temperatura',
             '20008' : 'Alimentazione di rete',
             '20009' : 'Limitazione corrente continua'
           } 

def date_decode(s):
  d = int(s[-2:], 16)
  m = int(s[-4:-2], 16)
  y = int(s[:-4], 16)
  return '%04d-%02d-%02d' % (y, m, d)

def time_decode(s):
  tsec = int(s, 16)
  h = tsec / 3600
  m = (tsec % 3600) / 60
  sec = tsec % 60
  return '%02d:%02d:%02d' % (h,m,sec)

def ecxx_print(s):
  sli = s.split(',')
  if len(sli) == 4 and sli[3] == '0' :
    tstamp = date_decode(sli[0]) + ' ' + time_decode(sli[1])
    try:
      edescr = logcodes[str(int(sli[2], 16))]
    except:
      edescr = str(int(sli[2], 16))
    return tstamp + ' - ' + edescr
  else :
    sys.stderr.write('Unsupported response: ' + s + '\n')
    return s

def pac_print(s):
  w = int(s, 16)
  return str(w/2)

def kwh_print(s):
  k = int(s, 16)
  return '%0.1f' % (k/10.0)

def kwt_print(s):
  k = int(s, 16)
  return str(k)

def typ_print(s):
  if s == '4E34' : return '3000S'
  elif s == '4E48' : return '6000S'
  else : return 'Unknown device'

def val_print(s):
  v = int(s, 16)
  return v

def vol_print(s):
  v = int(s, 16)
  return '%0.1f' % (v/10.0)

def stat_print(s):
  sli = s.split(',')
  if len(sli) == 4 :
    d = date_decode(sli[0])
    while d[-3:] == '-00' :
      d = d[:-3]
    k = kwh_print(sli[1])
    p = pac_print(sli[2])
    h = kwh_print(sli[3])
    return d + ': ' + k + ' kWh, ' + p + ' Wmax, ' + h + ' h'
  else :
    sys.stderr.write('Unsupported response: ' + s + '\n')
    return s

cmdd = {
        'CAC' : ['Numero accensioni', kwt_print, '#'],
        'PAC' : ['Potenza AC', pac_print, 'W'],
        'PDC' : ['Potenza DC', pac_print, 'W'],
        'PIN' : ['Potenza installata', pac_print, 'W'],
        'KDY' : ['Energia prodotta oggi', kwh_print, 'kWh'],
        'KLD' : ['Energia prodotta ieri', kwh_print, 'kWh'],
        'KLM' : ['Energia prodotta il mese scorso', kwt_print, 'kWh'],
        'KLY' : ['Energia prodotta l\'anno scorso', kwt_print, 'kWh'],
        'KMT' : ['Energia prodotta nel mese', kwt_print, 'kWh'],
        'KYR' : ['Energia prodotta nell\'anno', kwt_print, 'kWh'],
        'KT0' : ['Energia totale prodotta', kwt_print, 'kWh'],
        'KHR' : ['Tempo totale acceso', kwt_print, 'h'],
      	'TKK' : ['Maximum temprature', val_print, 'C'],
        'TYP' : ['Tipo apparato', typ_print, ''],
	    'UL1' : ['AC Voltage', vol_print, 'v']
    }

def crc16(s) :
    sum = 0
    for c in s :
        sum += ord(c)
    sum %= 2**16
    return '%04X' % (sum)

def crc_check(s) :
    crc_c = crc16(s[1:-5])
    crc = s[-5:-1]
    if crc_c == crc :
        return 1
    else :
        return 0

def request_string(devaddr, qrystr) :
  msglen = 19 + len(qrystr)
  hexlen = '%02X' % (msglen)
  reqmsg = 'FB;' + devaddr + ';' + hexlen + '|64:' + qrystr + '|'
  crc = crc16(reqmsg)
  final_reqmsg = '{' + reqmsg + crc + '}'
  return final_reqmsg

def response_to_pstringli(resp) :
  m = resp_ptrn.match(resp)
  if not m : return ['']
  if not crc_check(resp) : return ['']
  rli = m.group(1).split(';')
  retli = []
  for rr in rli :
    if rr == '' :
      retli.append('')
      continue
    lr = rr.split('=')
    if lr[0] in cmdd.keys() :
      pstr = cmdd[lr[0]][0] + ': ' + cmdd[lr[0]][1](lr[1]) + ' ' + cmdd[lr[0]][2]
    elif stat_cmd_ptrn.match(lr[0]) :
      pstr = lr[0] + '> ' + stat_print(lr[1])
    elif elog_cmd_ptrn.match(lr[0]) :
      pstr = lr[0] + '> ' + ecxx_print(lr[1])
    else :
      rrli = lr[1].split(',')
      if len(rrli) == 1 :
        pstr = rr + ' (dec: ' + str(int(lr[1], 16)) + ')'
      else :
        pstr = str(rrli)
    retli.append(pstr)
  return retli

def response_to_value(resp) :
  m = resp_ptrn.match(resp)
  if not m : return [[]]
  if not crc_check(resp) : return [[]]
  rli = m.group(1).split(';')
  retli = []
  for rr in rli :
    if rr == '' :
      retli.append([])
      continue
    lr = rr.split('=')
    if lr[0] in cmdd.keys() :
      dvu = cmdd[lr[0]][1](lr[1])
    elif stat_cmd_ptrn.match(lr[0]) :
      dvu = lr[0] + '> ' + stat_print(lr[1])
    elif elog_cmd_ptrn.match(lr[0]) :
      dvu = lr[0] + '> ' + ecxx_print(lr[1])
    else :
      dvu = str(rrli)
    retli.append(dvu)
  return retli

class SMConnection(object) :
  def __init__(self, ipaddr, tcpport, debug=1) :
    self.connected = 0
    self.recvbufsize = 1024
    self.debug = debug
    self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.sock.settimeout(5)
    try:
         self.sock.connect((ipaddr, tcpport))
    except:
         sys.stderr.write('Could not connect to Solarmax device.\n')
         return
    self.connected = 1

  def send(self, s) :
    self.sock.sendall(s.encode())
    if self.debug : sys.stderr.write('SMConn sent: ' + s + '\n')

  def receive(self) :
    s = self.sock.recv(self.recvbufsize)
    if self.debug : sys.stderr.write('SMConn recv: ' + s.decode() + '\n')
    return s.decode()

  def close(self) :
    self.sock.close()
    self.connected = 0
