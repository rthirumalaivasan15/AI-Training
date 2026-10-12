**Sunk-cost bias, named first:** a week went into the squad - orchestrator, two workers, hand-off ledger - and that week is why I want it to win; it is spent either way and is not evidence.
**Pass rate:** single agent **8/10**, squad **4/10** on the same 10 Week-6 cases and the same judge; the squad won no case the single agent lost.
**Bill:** **78,382 vs 47,339 tokens (1.7x)**, **$0.002384 vs $0.001234 per claim (1.9x)**; the coverage-worker hand-off alone (45,064 tok) costs 95% of the single agent's whole bill.
**Latency:** p50 **8.06 s vs 4.02 s**, p99 **11.04 s vs 6.20 s** - the slowest squad claim is slower than the slowest single-agent claim by 4.8 s.
**Where the quality went:** not synthesis (it kept the worker's position on 10/10 and carried the conditions) but the brief - the coverage worker, reading a summary of the notes instead of the notes, stopped at UNDETERMINED on C09 and C19 where the single agent decided correctly.
**Caveat:** n = 10, and the judge agreed with the labels 84% in Week 6; C01 and C06 lost with the same position as the single agent and may be judge noise - even then the squad is 6/10 vs 8/10 at 1.7x the tokens.
**Failure handling:** on an injected 500 it retried, then shipped NOT_IN_DOCUMENTS and hid the outage from the adjuster (failure_case.md).
**Verdict: kill the squad, keep the single agent.**
**Reopen only if** a squad beats 8/10 on these same 10 cases for no more than the single agent's 47,339 tokens.
