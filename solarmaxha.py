import mqttapi as mqtt
from datetime import datetime, timedelta
import json
import subprocess
from solarmax import *

ipaddr = "192.168.1.123"
tcpport = 12345
interval = 1
baseConfigTopic = 'homeassistant/sensor/solarmax_s3000p'
device = {
    "identifiers": "solarmax_s3000p",
    "manufacturer": "SolarMax",
    "model": "S3000p",
    "suggested_area": "roof"
}
autodiscoverypayload = {
    "device": device,
    "state_topic": "solarmax/state",
    "json_attributes_topic": "solarmax/status",
    "unique_id": "solarmax_s3000p",
    "name": "Solarmax S3000p"
}
sensorEnergyConfigTopic = baseConfigTopic+'/energy/config'
sensorEnergyConfig = {
    "device": device,
    "unit_of_measurement": "kWh",
    "device_class": "energy",
    "value_template": "{{ value_json.kwh_today }}",
    "state_topic": "solarmax/status",
    "name": "solarmax_s3000p_energy",
    "unique_id": "solarmax_s3000p_energy"
}
sensorVoltageConfigTopic = baseConfigTopic+'/voltage/config'
sensorVoltageConfig = {
    "device": device,
    "unit_of_measurement": "V",
    "device_class": "voltage",
    "value_template": "{{ value_json.volt_ac }}",
    "state_topic": "solarmax/status",
    "name": "solarmax_s3000p_voltage",
    "unique_id": "solarmax_s3000p_voltage"
}
sensorPowerConfigTopic = baseConfigTopic+'/power/config'
sensorPowerConfig = {
    "device": device,
    "unit_of_measurement": "W",
    "device_class": "power",
    "value_template": "{{ value_json.power_ac }}",
    "state_topic": "solarmax/status",
    "name": "solarmax_s3000p_power",
    "unique_id": "solarmax_s3000p_power"
}
sensorTemperatureConfigTopic = baseConfigTopic+'/temperature/config'
sensorTemperatureConfig = {
    "device": device,
    "unit_of_measurement": "°C",
    "device_class": "temperature",
    "value_template": "{{ value_json.temp }}",
    "state_topic": "solarmax/status",
    "name": "solarmax_s3000p_temperature",
    "unique_id": "solarmax_s3000p_temperature"
}


class SolarmaxHA(mqtt.Mqtt):

    def initialize(self):
        self.log("Initializing")
#        inOneMinute = datetime.now() + timedelta(minutes=1)

        self.mqtt_publish(baseConfigTopic+'/config', json.dumps(autodiscoverypayload))
        self.mqtt_publish(sensorEnergyConfigTopic, json.dumps(sensorEnergyConfig))
        self.mqtt_publish(sensorPowerConfigTopic, json.dumps(sensorPowerConfig))
        self.mqtt_publish(sensorVoltageConfigTopic, json.dumps(sensorVoltageConfig))
        self.mqtt_publish(sensorTemperatureConfigTopic, json.dumps(sensorTemperatureConfig))

        self.run_every(self.update, 'now', interval * 60)

    def update(self, args):
        if(self.sun_down()):
            self.mqtt_publish('solarmax/state', "OFF")
            return None

        try:
            spout = subprocess.check_output(
                ["ping", "-c", "1", "-W", "1", ipaddr], stderr=subprocess.STDOUT)
            self.mqtt_publish('solarmax/state', "ON")

            data = self.fetchData()

            if(data is not None):
                self.pushToMqtt(data)
            else:
                self.mqtt_publish('solarmax/state', "OFF")

        except subprocess.CalledProcessError:
            self.mqtt_publish('solarmax/state', "OFF")
            self.log('Solarmax IP is not responding.')

    def fetchData(self):
        smc = SMConnection(ipaddr, tcpport)
        if not smc.connected:
            return None

        device = SMDevice('S3000p', '00')

        return device.get_current_dict(smc)

    def pushToMqtt(self, object):
        self.log(json.dumps(object))
        self.mqtt_publish('solarmax/status', json.dumps(object))


class SMDevice(object):
    def __init__(self, name, address):
        self.name = name
        self.adr = address
        self.pac_now = 0
        self.temp = 0
        self.ac_volt = 0
        self.kwh_today = 0
        self.data_today = []  # kWh, Wmax, h ?
        self.dd_slist = []  # last days production
        self.dm_slist = []  # last months production

    def get_current_data(self, smc):
        smc.send(request_string(self.adr, 'PAC;KDY;DD00;UL1;TKK'))
        response = smc.receive()
        pstrli = response_to_value(response)
        if len(pstrli) == 5:
            self.pac_now = pstrli[0]
            self.kwh_today = pstrli[1]
            self.data_today = pstrli[2][6:]
            self.ac_volt = pstrli[3]
            self.temp = pstrli[4]
        smc.close()

    def get_current_dict(self, smc):
        cdict = {}
        self.get_current_data(smc)
        cdict['name'] = self.name
        cdict['addr'] = self.adr
        cdict['power_ac'] = self.pac_now
        cdict['temp'] = self.temp
        cdict['volt_ac'] = self.ac_volt
        cdict['kwh_today'] = self.kwh_today
        return cdict
