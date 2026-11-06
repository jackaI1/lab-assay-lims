import ctypes
import pathlib
import numpy as np


def align(source, target, initial=(0, 0, 0), library='build/libicp.so', max_distance=1.0):
    lib = ctypes.CDLL(str(pathlib.Path(library).resolve()))
    array = np.ctypeslib.ndpointer(dtype=np.float64, ndim=2, flags='C_CONTIGUOUS')
    vector = np.ctypeslib.ndpointer(dtype=np.float64, ndim=1, flags='C_CONTIGUOUS')
    lib.icp.argtypes = [array, ctypes.c_int, array, ctypes.c_int, vector, ctypes.c_int, ctypes.c_double]
    src = np.ascontiguousarray(source, dtype=np.float64); dst = np.ascontiguousarray(target, dtype=np.float64)
    result = np.array(initial, dtype=np.float64)
    status = lib.icp(src, len(src), dst, len(dst), result, 40, max_distance)
    if status: raise ValueError('ICP could not find enough correspondences')
    return result
