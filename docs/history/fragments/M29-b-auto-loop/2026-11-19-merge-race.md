**The merge race (ip#348, ip#363).** GitHub auto-merges a pull request the
moment both review checks go green. A few seconds later the loop asked for its
own `gh pr merge --auto`, which failed with "Pull Request is not mergeable"
because the pull request was already merged, and the loop then posted a stop
comment and added `needs-founder` to a merged pull request. When the merge call
fails with an error that is not a passing fault, the loop now reads the pull
request again. If GitHub reports it merged, the loop records it as done (the
same outcome as an auto-merge, so the merged event is still logged), logs the
race in one plain line, and posts no stop comment and no label. Any other
failure, including a pull request that is still open, stops as before. The
harness code and the fingerprints are unchanged.
