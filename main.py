
from machine import Pin, I2C, ADC
from bmp280 import BMP280
from umqtt.simple import MQTTClient
from time import sleep
import network
import dht
import gc

# ======================================
# CONFIGURACOES
# ======================================

SSID = "REDE-WIFI"
SENHA_WIFI = "SENHA-REDE-WIFI"

BROKER = "IP_DO_COMPUTADOR"
PORTA = 1884
USUARIO = "esp32"
SENHA_MQTT = "123456789"

INTERVALO = 5

# ======================================
# WI-FI
# ======================================

wifi = network.WLAN(network.STA_IF)
wifi.active(True)

def conectar_wifi():
    if wifi.isconnected():
        return True

    print("Conectando ao Wi-Fi...")

    try:
        wifi.disconnect()
    except Exception:
        pass

    try:
        wifi.connect(SSID, SENHA_WIFI)
    except Exception as erro:
        print("Erro ao iniciar Wi-Fi:", erro)
        return False

    for tentativa in range(20):
        if wifi.isconnected():
            print("Wi-Fi conectado!")
            print("IP:", wifi.ifconfig()[0])
            return True
        sleep(1)

    print("Wi-Fi indisponivel.")
    return False

# ======================================
# MQTT
# ======================================

cliente = None

def conectar_mqtt():
    global cliente

    if not conectar_wifi():
        return False

    print("Conectando ao MQTT...")

    novo_cliente = None

    try:
        novo_cliente = MQTTClient(
            client_id="esp32_estacao",
            server=BROKER,
            port=PORTA,
            user=USUARIO,
            password=SENHA_MQTT,
            keepalive=60
        )

        novo_cliente.connect()
        cliente = novo_cliente

        print("MQTT conectado!")
        return True

    except Exception as erro:
        print("Falha no MQTT:", erro)

        if novo_cliente is not None:
            try:
                novo_cliente.disconnect()
            except Exception:
                pass

        cliente = None
        return False

def publicar(topico, valor):
    global cliente

    if cliente is None or not wifi.isconnected():
        return False

    try:
        cliente.publish(
            topico.encode(),
            str(valor).encode()
        )
        return True

    except Exception as erro:
        print("Conexao MQTT perdida:", erro)

        try:
            cliente.disconnect()
        except Exception:
            pass

        cliente = None
        return False

# ======================================
# SENSORES
# ======================================

dht22 = dht.DHT22(Pin(4))

i2c = I2C(0, scl=Pin(22), sda=Pin(21))
bmp280 = None

try:
    dispositivos = i2c.scan()

    if 0x76 in dispositivos:
        bmp280 = BMP280(i2c, addr=0x76)
    elif 0x77 in dispositivos:
        bmp280 = BMP280(i2c, addr=0x77)
    else:
        print("BMP280 nao encontrado")

except Exception as erro:
    print("Erro BMP280:", erro)

chuva = ADC(Pin(34))
chuva.atten(ADC.ATTN_11DB)

gas = ADC(Pin(33))
gas.atten(ADC.ATTN_11DB)

ldr = ADC(Pin(35))
ldr.atten(ADC.ATTN_11DB)

# ======================================
# INICIALIZACAO
# ======================================

print("================================")
print("   ESTACAO METEOROLOGICA IoT")
print("================================")

conectar_mqtt()

# ======================================
# LOOP PRINCIPAL
# ======================================

while True:

    print("\n===== NOVAS MEDICOES =====")

    # Tenta reconectar antes das medicoes
    if cliente is None or not wifi.isconnected():
        conectar_mqtt()

    # DHT22
    try:
        dht22.measure()

        temperatura = dht22.temperature()
        umidade = dht22.humidity()

        print("Temperatura DHT22:", temperatura, "C")
        print("Umidade:", umidade, "%")

        publicar("estacao/temperatura", temperatura)
        publicar("estacao/umidade", umidade)

    except Exception as erro:
        print("Erro DHT22:", erro)

    # BMP280
    if bmp280 is not None:
        try:
            temperatura_bmp = bmp280.temperature
            pressao = round(bmp280.pressure / 100, 2)

            print("Temperatura BMP280:", temperatura_bmp)
            print("Pressao:", pressao, "hPa")

            publicar("estacao/temperatura_bmp", temperatura_bmp)
            publicar("estacao/pressao", pressao)

        except Exception as erro:
            print("Erro BMP280:", erro)

    # CHUVA
    try:
        valor_chuva = chuva.read()

        if valor_chuva >= 3000:
            estado = "SECO"
        elif valor_chuva >= 1500:
            estado = "UMIDO"
        else:
            estado = "CHUVA DETECTADA"

        print("Chuva ADC:", valor_chuva)
        print("Estado:", estado)

        publicar("estacao/chuva", estado)
        publicar("estacao/chuva_adc", valor_chuva)

    except Exception as erro:
        print("Erro chuva:", erro)

    # MQ-135
    try:
        valor_gas = gas.read()

        print("MQ-135 ADC:", valor_gas)
        publicar("estacao/gas_adc", valor_gas)

    except Exception as erro:
        print("Erro MQ-135:", erro)

    # LDR
    try:
        valor_luz = ldr.read()
        luminosidade = round(valor_luz / 4095 * 100, 1)

        print("LDR ADC:", valor_luz)
        print("Luminosidade:", luminosidade, "%")

        publicar("estacao/luminosidade", luminosidade)
        publicar("estacao/luminosidade_adc", valor_luz)

    except Exception as erro:
        print("Erro LDR:", erro)

    print("================================")

    gc.collect()
    sleep(INTERVALO)

