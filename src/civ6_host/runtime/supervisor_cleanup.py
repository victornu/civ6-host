"""Close owned pipes after the child is reaped, retaining flush failures."""
def close_reaped_process_pipes(process):
    if process.poll() is None:
        raise RuntimeError('Cannot clean pipes of a running native child')
    errors = []
    for name in ('stdin', 'stdout', 'stderr'):
        pipe = getattr(process, name)
        if pipe is None:
            continue
        try:
            pipe.close()
        except OSError as exc:
            # BufferedWriter.close can fail while flushing to a dead child.
            # Continue closing siblings and retain this diagnostic in the report.
            errors.append(dict(pipe=name,error=repr(exc),closed=bool(pipe.closed)))
    return errors
