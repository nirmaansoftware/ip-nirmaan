/* link.ld: the firmware image for nirmaan_soc.v. Everything lives in the
 * 64 KiB RAM at address 0, which the SoC loads from the image before reset
 * ends, so nothing is copied at startup; crt0.S only clears .bss. */
OUTPUT_ARCH(riscv)
ENTRY(_start)

MEMORY
{
    RAM (rwx) : ORIGIN = 0x00000000, LENGTH = 64K
}

SECTIONS
{
    .text : {
        KEEP(*(.text.start))
        *(.text .text.*)
    } > RAM
    .rodata : ALIGN(4) {
        *(.rodata .rodata.* .srodata .srodata.*)
    } > RAM
    .data : ALIGN(4) {
        __global_pointer$ = . + 0x800;
        *(.data .data.* .sdata .sdata.*)
    } > RAM
    .bss (NOLOAD) : ALIGN(4) {
        __bss_start = .;
        *(.bss .bss.* .sbss .sbss.* COMMON)
        . = ALIGN(4);
        __bss_end = .;
    } > RAM
    __stack_top = ORIGIN(RAM) + LENGTH(RAM);
    /DISCARD/ : { *(.comment) *(.riscv.attributes) }
}
