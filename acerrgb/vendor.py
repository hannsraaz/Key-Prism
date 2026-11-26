"""ctypes wrapper for InsydeDCHU.dll hardware communication.

Discovered signatures from DeviceIoControl/CppKeyboardColour and Insyde driver:
- T_SetDCHU_Data: DWORD (__stdcall*)(DWORD command, const UINT8* buffer, DWORD length)
- T_WriteAppSettings: DWORD (__stdcall*)(DWORD dwPage, DWORD dwOffset, DWORD dwLength, const UINT8* pInBuffer)
- T_ReadAppSettings: DWORD (__stdcall*)(DWORD dwPage, DWORD dwOffset, DWORD dwLength, UINT8* pOutBuffer)
- T_GetDCHU_Data_Integer: DWORD (__stdcall*)(DWORD command, DWORD* pOutValue)
- T_GetDCHU_Data_Buffer: DWORD (__stdcall*)(DWORD command, UINT8* pOutBuffer, DWORD length)
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_DLL_PATH = PROJECT_ROOT / "vendor" / "InsydeDCHU.dll"

# Known fallback locations on Acer Aspire 7 / CLEVO systems
DRIVERSTORE_FALLBACK = Path(
    r"C:\Windows\System32\DriverStore\FileRepository"
    r"\acpibridge1.inf_amd64_6172acb3e289f51f\InsydeDCHU.dll"
)
CONTROLCENTER_FALLBACK = Path(r"C:\Program Files (x86)\ControlCenter\InsydeDCHU.dll")


def find_dll(custom_path: Optional[Path | str] = None) -> Path:
    """Locate the InsydeDCHU.dll binary."""
    if custom_path:
        p = Path(custom_path).resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Specified DLL path does not exist: {p}")

    candidates = [
        VENDOR_DLL_PATH,
        DRIVERSTORE_FALLBACK,
        CONTROLCENTER_FALLBACK,
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(
        f"InsydeDCHU.dll not found in candidate paths:\n"
        + "\n".join(f" - {c}" for c in candidates)
        + "\nPlease ensure the DLL is placed at vendor/InsydeDCHU.dll."
    )


class DCHU:
    """Interface to Insyde DCHU DLL for hardware lighting and settings control."""

    def __init__(self, dll_path: Optional[Path | str] = None):
        self.dll_path = find_dll(dll_path)
        logger.debug("Loading Insyde DCHU DLL from: %s", self.dll_path)
        self.dll = ctypes.WinDLL(str(self.dll_path))

        self._init_function_signatures()

    def _init_function_signatures(self):
        """Set up explicit ctypes signatures discovered from C++ reference source."""
        # DWORD SetDCHU_Data(DWORD command, const UINT8* buffer, DWORD length);
        if hasattr(self.dll, "SetDCHU_Data"):
            self._set_data = self.dll.SetDCHU_Data
            self._set_data.argtypes = [
                ctypes.c_uint32,  # command
                ctypes.c_char_p,  # buffer
                ctypes.c_uint32,  # length
            ]
            self._set_data.restype = ctypes.c_uint32
        else:
            self._set_data = None
            logger.warning("SetDCHU_Data export not found in DLL")

        # DWORD WriteAppSettings(DWORD dwPage, DWORD dwOffset, DWORD dwLength, const UINT8* pInBuffer);
        if hasattr(self.dll, "WriteAppSettings"):
            self._write_app_settings = self.dll.WriteAppSettings
            self._write_app_settings.argtypes = [
                ctypes.c_uint32,  # dwPage
                ctypes.c_uint32,  # dwOffset
                ctypes.c_uint32,  # dwLength
                ctypes.c_char_p,  # pInBuffer
            ]
            self._write_app_settings.restype = ctypes.c_uint32
        else:
            self._write_app_settings = None
            logger.warning("WriteAppSettings export not found in DLL")

        # DWORD ReadAppSettings(DWORD dwPage, DWORD dwOffset, DWORD dwLength, UINT8* pOutBuffer);
        if hasattr(self.dll, "ReadAppSettings"):
            self._read_app_settings = self.dll.ReadAppSettings
            self._read_app_settings.argtypes = [
                ctypes.c_uint32,  # dwPage
                ctypes.c_uint32,  # dwOffset
                ctypes.c_uint32,  # dwLength
                ctypes.POINTER(ctypes.c_uint8),  # pOutBuffer
            ]
            self._read_app_settings.restype = ctypes.c_uint32
        else:
            self._read_app_settings = None

        # DWORD GetDCHU_Data_Integer(DWORD command, DWORD* pOut);
        if hasattr(self.dll, "GetDCHU_Data_Integer"):
            self._get_integer = self.dll.GetDCHU_Data_Integer
            self._get_integer.argtypes = [
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            self._get_integer.restype = ctypes.c_uint32
        else:
            self._get_integer = None

        # DWORD GetDCHU_Data_Buffer(DWORD command, UINT8* buffer, DWORD length);
        if hasattr(self.dll, "GetDCHU_Data_Buffer"):
            self._get_buffer = self.dll.GetDCHU_Data_Buffer
            self._get_buffer.argtypes = [
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint8),
                ctypes.c_uint32,
            ]
            self._get_buffer.restype = ctypes.c_uint32
        else:
            self._get_buffer = None

    def set_dchu_data(self, command: int, data: bytes) -> int:
        """Call SetDCHU_Data with command ID and raw bytes buffer."""
        if self._set_data is None:
            raise RuntimeError("SetDCHU_Data function not available in loaded DLL")
        logger.debug(
            "Calling SetDCHU_Data(command=0x%X, length=%d, data=%s)",
            command, len(data), list(data)
        )
        return self._set_data(command, data, len(data))

    def write_app_settings(self, page: int, offset: int, data: bytes) -> int:
        """Call WriteAppSettings with page, offset, and raw bytes buffer."""
        if self._write_app_settings is None:
            raise RuntimeError("WriteAppSettings function not available in loaded DLL")
        logger.debug(
            "Calling WriteAppSettings(page=%d, offset=0x%X, length=%d, data=%s)",
            page, offset, len(data), list(data)
        )
        return self._write_app_settings(page, offset, len(data), data)

    def read_app_settings(self, page: int, offset: int, length: int) -> bytes:
        """Call ReadAppSettings with page, offset, and requested length."""
        if self._read_app_settings is None:
            raise RuntimeError("ReadAppSettings function not available in loaded DLL")
        buf = (ctypes.c_uint8 * length)()
        res = self._read_app_settings(page, offset, length, buf)
        logger.debug(
            "ReadAppSettings(page=%d, offset=0x%X, length=%d) -> result=%d",
            page, offset, length, res
        )
        return bytes(buf)

    def get_dchu_integer(self, command: int) -> tuple[int, int]:
        """Call GetDCHU_Data_Integer. Returns (status_code, integer_value)."""
        if self._get_integer is None:
            raise RuntimeError("GetDCHU_Data_Integer not available in loaded DLL")
        val = ctypes.c_uint32(0)
        res = self._get_integer(command, ctypes.byref(val))
        return (res, val.value)

    def get_dchu_buffer(self, command: int, length: int) -> tuple[int, bytes]:
        """Call GetDCHU_Data_Buffer. Returns (status_code, buffer_bytes)."""
        if self._get_buffer is None:
            raise RuntimeError("GetDCHU_Data_Buffer not available in loaded DLL")
        buf = (ctypes.c_uint8 * length)()
        res = self._get_buffer(command, buf, length)
        return (res, bytes(buf))

    def status(self) -> dict[str, Any]:
        """Return status dictionary of loaded DLL and available exports."""
        return {
            "dll_path": str(self.dll_path),
            "SetDCHU_Data": self._set_data is not None,
            "WriteAppSettings": self._write_app_settings is not None,
            "ReadAppSettings": self._read_app_settings is not None,
            "GetDCHU_Data_Integer": self._get_integer is not None,
            "GetDCHU_Data_Buffer": self._get_buffer is not None,
        }
