/*
 * string.h for the bare-metal RISC-V image: the memory functions a compiler
 * may call on its own even in freestanding code (see nirmaan_libc.c).
 */
#ifndef NIRMAAN_LIBC_STRING_H
#define NIRMAAN_LIBC_STRING_H

#include <stddef.h>

void *memcpy(void *restrict dst, const void *restrict src, size_t n);
void *memmove(void *dst, const void *src, size_t n);
void *memset(void *dst, int c, size_t n);
int memcmp(const void *a, const void *b, size_t n);
size_t strlen(const char *s);

#endif /* NIRMAAN_LIBC_STRING_H */
