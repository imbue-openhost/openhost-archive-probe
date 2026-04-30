# archive-probe

Throwaway test app for verifying the OpenHost `app_archive` storage tier.

It reports what it sees under `/data/app_data` and `/data/app_archive`, and
writes a marker file into each so that the host filesystem can be inspected to
confirm the bind mounts.
