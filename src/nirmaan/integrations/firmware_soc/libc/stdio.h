/*
 * stdio.h for the bare-metal RISC-V image: the part of the C library the
 * SoC runtime supplies (see nirmaan_libc.c). A driver or test that calls
 * anything else fails to link, and the failed link is a recorded run naming
 * the symbol.
 */
#ifndef NIRMAAN_LIBC_STDIO_H
#define NIRMAAN_LIBC_STDIO_H

#include <stdarg.h>
#include <stddef.h>

int snprintf(char *restrict out, size_t size, const char *restrict format, ...);
int vsnprintf(char *restrict out, size_t size, const char *restrict format, va_list args);

#endif /* NIRMAAN_LIBC_STDIO_H */
