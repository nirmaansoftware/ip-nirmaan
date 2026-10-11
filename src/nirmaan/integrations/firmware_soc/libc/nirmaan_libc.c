/*
 * nirmaan_libc.c: the small C library of the bare-metal RISC-V image.
 *
 * No libc ships with every RISC-V GCC (Homebrew's has none; Ubuntu's comes
 * with picolibc as a separate package), so the SoC runtime carries the little
 * a driver test needs: snprintf and vsnprintf, with the flags '-' and '0', a
 * field width, the length modifiers hh, h, l, ll, and z, and the conversions
 * d, i, u, x, X, o, c, s, p, and %; and the memory functions GCC may call on
 * its own. Anything else is a link error, never a silent stub.
 */
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef struct sink {
    char *out;
    size_t size;
    size_t length; /* characters the full result needs, as C requires */
} sink;

static void emit(sink *s, char c) {
    if (s->size != 0u && s->length < s->size - 1u) {
        s->out[s->length] = c;
    }
    ++s->length;
}

static void pad(sink *s, char c, int count) {
    while (count-- > 0) {
        emit(s, c);
    }
}

static void emit_text(sink *s, const char *text, size_t n, int width, int left) {
    size_t i;
    int fill = width > (int)n ? width - (int)n : 0;
    if (!left) {
        pad(s, ' ', fill);
    }
    for (i = 0; i < n; ++i) {
        emit(s, text[i]);
    }
    if (left) {
        pad(s, ' ', fill);
    }
}

static void emit_number(sink *s, unsigned long long value, int negative, unsigned base, int upper, int width,
                        int left, int zero) {
    const char *digits = upper ? "0123456789ABCDEF" : "0123456789abcdef";
    char buffer[24];
    int n = 0;
    int length;
    do {
        buffer[n++] = digits[value % base];
        value /= base;
    } while (value != 0u);
    length = n + (negative ? 1 : 0);
    if (!left && !zero) {
        pad(s, ' ', width - length);
    }
    if (negative) {
        emit(s, '-');
    }
    if (!left && zero) {
        pad(s, '0', width - length);
    }
    while (n > 0) {
        emit(s, buffer[--n]);
    }
    if (left) {
        pad(s, ' ', width - length);
    }
}

int vsnprintf(char *restrict out, size_t size, const char *restrict format, va_list args) {
    sink s = {out, size, 0u};
    const char *p = format;
    while (*p != '\0') {
        int left = 0, zero = 0, width = 0, longs = 0, shorts = 0, sized = 0;
        if (*p != '%') {
            emit(&s, *p++);
            continue;
        }
        ++p;
        for (;; ++p) {
            if (*p == '-') {
                left = 1;
            } else if (*p == '0') {
                zero = 1;
            } else {
                break;
            }
        }
        while (*p >= '0' && *p <= '9') {
            width = width * 10 + (*p++ - '0');
        }
        for (;; ++p) {
            if (*p == 'l') {
                ++longs;
            } else if (*p == 'h') {
                ++shorts;
            } else if (*p == 'z') {
                sized = 1;
            } else {
                break;
            }
        }
        switch (*p) {
        case 'd':
        case 'i': {
            long long v = longs >= 2 ? va_arg(args, long long)
                          : longs == 1 ? va_arg(args, long)
                          : sized ? (long long)va_arg(args, size_t)
                                  : va_arg(args, int);
            if (shorts == 1) {
                v = (short)v;
            } else if (shorts >= 2) {
                v = (signed char)v;
            }
            emit_number(&s, v < 0 ? 0u - (unsigned long long)v : (unsigned long long)v, v < 0, 10u, 0, width,
                        left, zero);
            break;
        }
        case 'u':
        case 'x':
        case 'X':
        case 'o': {
            unsigned long long v = longs >= 2 ? va_arg(args, unsigned long long)
                                   : longs == 1 ? va_arg(args, unsigned long)
                                   : sized ? va_arg(args, size_t)
                                           : va_arg(args, unsigned int);
            unsigned base = *p == 'u' ? 10u : *p == 'o' ? 8u : 16u;
            if (shorts == 1) {
                v = (unsigned short)v;
            } else if (shorts >= 2) {
                v = (unsigned char)v;
            }
            emit_number(&s, v, 0, base, *p == 'X', width, left, zero);
            break;
        }
        case 'p':
            emit(&s, '0');
            emit(&s, 'x');
            emit_number(&s, (uintptr_t)va_arg(args, void *), 0, 16u, 0, width, left, zero);
            break;
        case 'c': {
            char c = (char)va_arg(args, int);
            emit_text(&s, &c, 1u, width, left);
            break;
        }
        case 's': {
            const char *text = va_arg(args, const char *);
            if (text == NULL) {
                text = "(null)";
            }
            emit_text(&s, text, strlen(text), width, left);
            break;
        }
        case '%':
            emit(&s, '%');
            break;
        case '\0':
            --p; /* a lone '%' at the end: stop at the terminator below */
            break;
        default: /* an unsupported conversion is printed as written, so the log shows it */
            emit(&s, '%');
            emit(&s, *p);
            break;
        }
        ++p;
    }
    if (size != 0u) {
        out[s.length < size ? s.length : size - 1u] = '\0';
    }
    return (int)s.length;
}

int snprintf(char *restrict out, size_t size, const char *restrict format, ...) {
    va_list args;
    int n;
    va_start(args, format);
    n = vsnprintf(out, size, format, args);
    va_end(args);
    return n;
}

void *memcpy(void *restrict dst, const void *restrict src, size_t n) {
    unsigned char *d = dst;
    const unsigned char *s = src;
    while (n-- > 0u) {
        *d++ = *s++;
    }
    return dst;
}

void *memmove(void *dst, const void *src, size_t n) {
    unsigned char *d = dst;
    const unsigned char *s = src;
    if (d < s) {
        while (n-- > 0u) {
            *d++ = *s++;
        }
    } else {
        while (n-- > 0u) {
            d[n] = s[n];
        }
    }
    return dst;
}

void *memset(void *dst, int c, size_t n) {
    unsigned char *d = dst;
    while (n-- > 0u) {
        *d++ = (unsigned char)c;
    }
    return dst;
}

int memcmp(const void *a, const void *b, size_t n) {
    const unsigned char *x = a;
    const unsigned char *y = b;
    for (; n > 0u; --n, ++x, ++y) {
        if (*x != *y) {
            return *x < *y ? -1 : 1;
        }
    }
    return 0;
}

size_t strlen(const char *s) {
    size_t n = 0u;
    while (s[n] != '\0') {
        ++n;
    }
    return n;
}
