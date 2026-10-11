/*
 * axil_timer_map.h: the register map of axil_timer (axil_timer.v header).
 */
#ifndef AXIL_TIMER_MAP_H
#define AXIL_TIMER_MAP_H

#define AXIL_TIMER_CTRL_OFFSET 0x0u
#define AXIL_TIMER_LOAD_OFFSET 0x4u
#define AXIL_TIMER_COUNT_OFFSET 0x8u /* read only: a write is SLVERR */
#define AXIL_TIMER_STATUS_OFFSET 0xCu

#define AXIL_TIMER_CTRL_EN 0x1u /* writing 1 loads COUNT from LOAD and starts */
#define AXIL_TIMER_CTRL_IE 0x2u /* interrupt enable */
#define AXIL_TIMER_STATUS_EXPIRED 0x1u /* write 1 to clear */

#endif /* AXIL_TIMER_MAP_H */
