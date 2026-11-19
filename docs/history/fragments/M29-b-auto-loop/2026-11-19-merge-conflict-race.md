**The merge call that meets a levels.json conflict.** Each record pull request
regenerates `capability/levels.json`. When main moved after the loop had looked
but before it armed auto-merge, `gh pr merge --auto` failed with "Pull Request
has merge conflicts" and the loop stopped the pull request with `needs-founder`,
although the only conflict was the generated file the loop already resolves
during a branch update (ip#263). On that error the loop now reads the pull
request again. If GitHub reports the conflict at the same head and the loop's
own detection says it is only the generated file, it makes the same branch
update and regeneration, and the new head is reviewed from scratch: no stop, no
label. Any other conflict, an unreadable pull request or a moved head stops as
before. The harness code and the fingerprints are unchanged.
