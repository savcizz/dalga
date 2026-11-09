"""
apex_hid.py - Apex 3 TKL ile dogrudan USB (HID) iletisim katmani
Sadece Windows'un kendi DLL'lerini kullanir (ctypes). pip install GEREKMEZ.
"""

import ctypes

VID = 0x1038
PID = 0x1622  # Apex 3 TKL

setupapi = ctypes.WinDLL("setupapi", use_last_error=True)
hid = ctypes.WinDLL("hid", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

c_void_p = ctypes.c_void_p
byref = ctypes.byref


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_uint32),
        ("Data2", ctypes.c_uint16),
        ("Data3", ctypes.c_uint16),
        ("Data4", ctypes.c_ubyte * 8),
    ]


class SP_DEVICE_INTERFACE_DATA(ctypes.Structure):
    _fields_ = [
        ("cbSize", ctypes.c_uint32),
        ("InterfaceClassGuid", GUID),
        ("Flags", ctypes.c_uint32),
        ("Reserved", c_void_p),
    ]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [
        ("Size", ctypes.c_uint32),
        ("VendorID", ctypes.c_uint16),
        ("ProductID", ctypes.c_uint16),
        ("VersionNumber", ctypes.c_uint16),
    ]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", ctypes.c_uint16),
        ("UsagePage", ctypes.c_uint16),
        ("InputReportByteLength", ctypes.c_uint16),
        ("OutputReportByteLength", ctypes.c_uint16),
        ("FeatureReportByteLength", ctypes.c_uint16),
        ("Reserved", ctypes.c_uint16 * 17),
        ("NumberLinkCollectionNodes", ctypes.c_uint16),
        ("NumberInputButtonCaps", ctypes.c_uint16),
        ("NumberInputValueCaps", ctypes.c_uint16),
        ("NumberInputDataIndices", ctypes.c_uint16),
        ("NumberOutputButtonCaps", ctypes.c_uint16),
        ("NumberOutputValueCaps", ctypes.c_uint16),
        ("NumberOutputDataIndices", ctypes.c_uint16),
        ("NumberFeatureButtonCaps", ctypes.c_uint16),
        ("NumberFeatureValueCaps", ctypes.c_uint16),
        ("NumberFeatureDataIndices", ctypes.c_uint16),
    ]


hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
hid.HidD_GetHidGuid.restype = None
hid.HidD_GetAttributes.argtypes = [c_void_p, ctypes.POINTER(HIDD_ATTRIBUTES)]
hid.HidD_GetAttributes.restype = ctypes.c_ubyte
hid.HidD_GetPreparsedData.argtypes = [c_void_p, ctypes.POINTER(c_void_p)]
hid.HidD_GetPreparsedData.restype = ctypes.c_ubyte
hid.HidD_FreePreparsedData.argtypes = [c_void_p]
hid.HidD_FreePreparsedData.restype = ctypes.c_ubyte
hid.HidP_GetCaps.argtypes = [c_void_p, ctypes.POINTER(HIDP_CAPS)]
hid.HidP_GetCaps.restype = ctypes.c_int32

setupapi.SetupDiGetClassDevsW.argtypes = [
    ctypes.POINTER(GUID), ctypes.c_wchar_p, c_void_p, ctypes.c_uint32,
]
setupapi.SetupDiGetClassDevsW.restype = c_void_p
setupapi.SetupDiEnumDeviceInterfaces.argtypes = [
    c_void_p, c_void_p, ctypes.POINTER(GUID), ctypes.c_uint32,
    ctypes.POINTER(SP_DEVICE_INTERFACE_DATA),
]
setupapi.SetupDiEnumDeviceInterfaces.restype = ctypes.c_int
setupapi.SetupDiGetDeviceInterfaceDetailW.argtypes = [
    c_void_p, ctypes.POINTER(SP_DEVICE_INTERFACE_DATA), c_void_p,
    ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), c_void_p,
]
setupapi.SetupDiGetDeviceInterfaceDetailW.restype = ctypes.c_int
setupapi.SetupDiDestroyDeviceInfoList.argtypes = [c_void_p]
setupapi.SetupDiDestroyDeviceInfoList.restype = ctypes.c_int

kernel32.CreateFileW.argtypes = [
    ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, c_void_p,
    ctypes.c_uint32, ctypes.c_uint32, c_void_p,
]
kernel32.CreateFileW.restype = c_void_p
kernel32.WriteFile.argtypes = [
    c_void_p, c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32), c_void_p,
]
kernel32.WriteFile.restype = ctypes.c_int
kernel32.CloseHandle.argtypes = [c_void_p]
kernel32.CloseHandle.restype = ctypes.c_int

INVALID = c_void_p(-1).value
OPEN_EXISTING = 3
SHARE_RW = 3
GENERIC_RW = 0xC0000000


def _ac(yol, erisim):
    h = kernel32.CreateFileW(yol, erisim, SHARE_RW, None, OPEN_EXISTING, 0, None)
    if h is None or h == INVALID:
        return None
    return h


def cihazlari_bul():
    """Klavyenin tum HID arayuzlerini listeler."""
    guid = GUID()
    hid.HidD_GetHidGuid(byref(guid))
    info = setupapi.SetupDiGetClassDevsW(byref(guid), None, None, 0x12)
    sonuc = []
    i = 0
    while True:
        d = SP_DEVICE_INTERFACE_DATA()
        d.cbSize = ctypes.sizeof(d)
        if not setupapi.SetupDiEnumDeviceInterfaces(info, None, byref(guid), i, byref(d)):
            break
        i += 1
        gerekli = ctypes.c_uint32(0)
        setupapi.SetupDiGetDeviceInterfaceDetailW(info, byref(d), None, 0, byref(gerekli), None)
        buf = ctypes.create_string_buffer(gerekli.value)
        ctypes.c_uint32.from_buffer(buf).value = 8 if ctypes.sizeof(c_void_p) == 8 else 6
        if not setupapi.SetupDiGetDeviceInterfaceDetailW(info, byref(d), buf, gerekli, None, None):
            continue
        yol = ctypes.wstring_at(ctypes.addressof(buf) + 4)

        h = _ac(yol, 0)
        if h is None:
            continue
        try:
            att = HIDD_ATTRIBUTES()
            att.Size = ctypes.sizeof(att)
            if not hid.HidD_GetAttributes(h, byref(att)):
                continue
            if att.VendorID != VID or att.ProductID != PID:
                continue
            pre = c_void_p()
            if not hid.HidD_GetPreparsedData(h, byref(pre)):
                continue
            try:
                caps = HIDP_CAPS()
                hid.HidP_GetCaps(pre, byref(caps))
            finally:
                hid.HidD_FreePreparsedData(pre)
            sonuc.append({
                "yol": yol,
                "usage_page": caps.UsagePage,
                "usage": caps.Usage,
                "out_len": caps.OutputReportByteLength,
            })
        finally:
            kernel32.CloseHandle(h)
    setupapi.SetupDiDestroyDeviceInfoList(info)
    return sonuc


def paket(renkler):
    """[rapor_id=0, komut=0x21, bolge_maskesi=0xFF, 8 x (R,G,B), sifirlar] = 65 bayt"""
    p = bytearray(65)
    p[1] = 0x21
    p[2] = 0xFF
    for i, (r, g, b) in enumerate(renkler[:8]):
        p[3 + 3 * i: 6 + 3 * i] = bytes((r, g, b))
    return bytes(p)


class ApexKlavye:
    """Klavyeye renk gonderir. Baglanti koparsa kendini yeniden baglar."""

    def __init__(self):
        self.h = None
        self.out_len = 65

    def baglan(self):
        liste = cihazlari_bul()
        # Once bilinen calisan arayuz (usage_page 0xFFC0, usage 1), sonra benzer ozel arayuzler
        adaylar = [c for c in liste if c["usage_page"] == 0xFFC0 and c["usage"] == 1]
        adaylar += [c for c in liste if c["usage_page"] >= 0xFF00 and c not in adaylar]
        for c in adaylar:
            if c["out_len"] <= 0:
                continue
            h = _ac(c["yol"], GENERIC_RW)
            if h is not None:
                self.h = h
                self.out_len = c["out_len"]
                return True
        return False

    def renk_gonder(self, renkler):
        """8 bolgenin renklerini gonderir. Basarili ise True."""
        if self.h is None and not self.baglan():
            return False
        veri = paket(renkler)[: self.out_len].ljust(self.out_len, b"\x00")
        buf = ctypes.create_string_buffer(veri, self.out_len)
        yazilan = ctypes.c_uint32(0)
        ok = kernel32.WriteFile(self.h, buf, self.out_len, byref(yazilan), None)
        if not ok:
            self.kapat()
            return False
        return True

    def kapat(self):
        if self.h is not None:
            kernel32.CloseHandle(self.h)
            self.h = None
