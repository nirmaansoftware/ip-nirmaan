# Requirements: `counter`

The requirements specification `drive` writes for every requirements stage
(M38). Each requirement a verification plan must cover ends with its tag.

## 1. Function

* The count resets to zero while `rst` is high. [req:CNT-RESET]
* While `en` is high the count advances by one each clock and wraps to zero after `LIMIT`. [req:CNT-COUNT]

## 2. Implementation

* The design synthesizes with no latches. [req:CNT-SYNTH]
