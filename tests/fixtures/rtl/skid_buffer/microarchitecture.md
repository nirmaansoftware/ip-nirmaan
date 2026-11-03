# Microarchitecture: `skid_buffer`

The implementation plan for the interface in `interface_spec.md`. The RTL is
`skid_buffer.v`.

## 1. Why two registers

A single pipeline register that loads whenever it is empty or its beat
leaves needs `s_ready = !m_valid || m_ready`: a combinational path from the
receiver's ready to the sender. Registering that ready instead means the
slice decides one cycle ahead whether it can take a beat, so in the cycle the
output stalls it may already have said yes. The second register, the skid
register, catches that beat. Two registers are the least that give full
throughput with every output from a flop.

## 2. State

| Register | Reset | Meaning |
|---|---|---|
| `m_valid` | 0 | the output register holds a beat |
| `m_data` | none | that beat |
| `skid_valid` | 0 | the skid register holds a beat |
| `skid_data` | none | that beat, always the newer of two |

The skid register is only ever full while the output register is full, so
the slice holds `m_valid + skid_valid` beats. `s_ready = !skid_valid`.

## 3. Next state

Let `m_free = !m_valid || m_ready` (the output register may load on this
edge) and `s_fire = s_valid && s_ready`.

| Case | `m_valid`, `m_data` | `skid_valid`, `skid_data` |
|---|---|---|
| reset | `m_valid` 0 | `skid_valid` 0 |
| `m_free` and `skid_valid` | load the skid beat | empty |
| `m_free`, skid empty | load `s_data`; `m_valid <= s_valid` | stay empty |
| not `m_free` and `s_fire` | hold | load `s_data` |
| not `m_free`, no `s_fire` | hold | hold |

When the skid register is full, `s_ready` is low, so the second row never
has an input beat to place: on that edge the skid beat moves to the output
register and `s_ready` rises. On the next edge the skid beat leaves and a new
beat takes its place in the output register, so the receiver sees no bubble.

The data registers are not reset; each loads only in its control's row, so
`m_data` never changes while a beat is offered and not taken.

## 4. Timing

Every output is a flop or the inverse of one. The inputs reach only the next
state: `m_ready` and `s_valid` select which register loads, and `s_data`
reaches two register inputs through one multiplexer.

## 5. Verification plan

| Check | Tool | File |
|---|---|---|
| Lint, `-Wall`, no waivers, `WIDTH` 8 and 1 | Verilator | `skid_buffer.v` |
| Directed and random self-checking simulation, lanes at `WIDTH` 8 and 1 | Icarus and Verilator | `skid_buffer_tb.v` |
| Synthesis, no latches | Yosys | `skid_buffer.v` |
| Queue and output properties, unbounded proof, `WIDTH` 8 | SymbiYosys | `skid_buffer.sby` |
| The same properties at `WIDTH` 1 | SymbiYosys | `skid_buffer_w1.sby` |

The testbench keeps a list of the beats the slice accepted and checks every
cycle that the outputs match it: `m_valid` while beats are held, `s_ready`
while fewer than two are, `m_data` the oldest, and a stalled beat unchanged.
Before each edge it flips `m_ready` and `s_valid` for a nanosecond and checks
that `s_ready` does not move.

The formal block (under `ifdef FORMAL`) keeps its own queue of up to two
beats, moved only by the handshakes at the ports, and asserts after every
edge that `m_valid`, `s_ready` and `m_data` agree with it, that a stalled
beat holds, and, inside, that the skid register holds the newer beat whenever
two are held. It assumes nothing about the sender or the receiver.
