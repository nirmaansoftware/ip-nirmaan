**A `--records` key that matches no record is refused.** The checker used to
treat a path, a typo or an empty `--records` as a batch of nothing: it printed
"model-labelled failures in scope: 0" and exited 0, the same fault that hid two
failures of the W2-L1 batch (wave 2 close, action A7). It now prints the unknown
keys and exits 2, before it lists anything. A record is a folder that holds a
trial, passing ones included, or a `causes.md`. The harness code and the
fingerprints are unchanged.
