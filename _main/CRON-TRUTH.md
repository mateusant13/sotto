# CRON-TRUTH: is `d43fb9be-283d-4dd3-8e73-d9fb562fd181` actually delivering?

Status: IN PROGRESS (receipt opened 2026-10-07, lane/cront)
Verdict: UNKNOWN (pending investigation)

## Question
The consolidated cron `d43fb9be-283d-4dd3-8e73-d9fb562fd181` is ARMED
(state=active, schedule `*/3`) but zero firings have been observed.
The owner's continuity plan rests on this firing.

## Known limit under test
The scheduler hydrates from the store only at process start
(`restoreActiveJobs`, in-memory Map). A row written while mcode is
already running does not fire until the next start. "Did not fire" may
therefore be expected behaviour rather than a defect.

## Findings
(filled in below as the investigation proceeds)

## Verdict
To be filled in: FIRES / NEVER-FIRES / HYDRATION-LIMIT-EXPLAINS / UNKNOWN