"OS Error map"

from __future__ import annotations

os_error_mapping = {
    1: ("EPERM", "Operation not permitted"),
    2: ("ENOENT", "No such file or directory"),
    3: ("ESRCH", "No such process"),
    4: ("EINTR", "Interrupted system call"),
    5: ("EIO", "I/O error"),
    6: ("ENXIO", "No such device or address"),
    7: ("E2BIG", "Argument list too long"),
    8: ("ENOEXEC", "Exec format error"),
    9: ("EBADF", "Bad file number"),
    10: ("ECHILD", "No child processes"),
    11: ("EAGAIN", "Try again"),
    12: ("ENOMEM", "Out of memory"),
    13: ("EACCES", "Permission denied"),
    14: ("EFAULT", "Bad address"),
    15: ("ENOTBLK", "Block device required"),
    16: ("EBUSY", "Device or resource busy"),
    17: ("EEXIST", "File exists"),
    18: ("EXDEV", "Cross-device link"),
    19: ("ENODEV", "No such device"),
    20: ("ENOTDIR", "Not a directory"),
    21: ("EISDIR", "Is a directory"),
    22: ("EINVAL", "Invalid argument"),
    23: ("ENFILE", "File table overflow"),
    24: ("EMFILE", "Too many open files"),
    25: ("ENOTTY", "Not a typewriter"),
    26: ("ETXTBSY", "Text file busy"),
    27: ("EFBIG", "File too large"),
    28: ("ENOSPC", "No space left on device"),
    29: ("ESPIPE", "Illegal seek"),
    30: ("EROFS", "Read-only file system"),
    31: ("EMLINK", "Too many links"),
    32: ("EPIPE", "Broken pipe"),
    33: ("EDOM", "Math argument out of domain of func"),
    34: ("ERANGE", "Math result not representable"),
    # E'EWOULDBLOCK', AGAIN: ('operation would block'),
    95: ("EOPNOTSUPP", "Operation not supported on transport endpoint"),
    97: ("EAFNOSUPPORT", "Address family not supported by protocol"),
    98: ("EADDRINUSE", "Address already in use"),
    103: ("ECONNABORTED", "Software caused connection abort"),
    104: ("ECONNRESET", "Connection reset by peer"),
    105: ("ENOBUFS", "No buffer space available"),
    106: ("EISCONN", "Transport endpoint is already connected"),
    107: ("ENOTCONN", "Transport endpoint is not connected"),
    110: ("ETIMEDOUT", "Connection timed out"),
    111: ("ECONNREFUSED", "Connection refused"),
    113: ("EHOSTUNREACH", "No route to host"),
    114: ("EALREADY", "Operation already in progress"),
    115: ("EINPROGRESS", "Operation now in progress"),
}
