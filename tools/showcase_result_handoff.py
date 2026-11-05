"""Bounded local evidence reads; never sends/replays a hardware transaction."""
import json,time


def read_result(path, deadline, clock=time.monotonic, pause=time.sleep):
    while True:
        try:
            return json.loads(path.read_text(encoding='utf-8'))
        except PermissionError:
            # Windows can briefly deny a read immediately after atomic replace.
            # Reopen only this already-produced artifact, never resend the job.
            remaining=deadline-clock()
            if remaining<=0:
                raise
            pause(min(.05,remaining))
