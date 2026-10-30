#!/usr/bin/env python3
"""Cache public local-ASR dependencies through the runtime's normal HTTPS stack.

No credentials, audio uploads, inference API calls, TLS overrides or generation.
Only GETs to the same public CDN/model hosts allowed by the isolated test.
"""
import hashlib
import os
from pathlib import Path
import sys
import urllib.parse
import urllib.request


def allowed(url):
    parsed = urllib.parse.urlsplit(url)
    host = parsed.hostname or ''
    return (parsed.scheme == 'https' and not parsed.username and not parsed.password
            and (host in ['cdn.jsdelivr.net', 'unpkg.com', 'huggingface.co']
                 or host.endswith('.huggingface.co') or host.endswith('.hf.co')))


class PublicRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl):
            raise ValueError('Model redirect host is not permitted')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def cache(url, directory):
    if not allowed(url):
        raise ValueError('Only approved public HTTPS dependency hosts are permitted')
    folder = Path(directory)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder/hashlib.sha256(url.encode()).hexdigest()
    if target.is_file():
        return target
    temporary = target.with_name(target.name+f'.{os.getpid()}.part')
    total = 0
    try:
        opener = urllib.request.build_opener(PublicRedirect())
        with opener.open(url, timeout=90) as source, temporary.open('xb') as output:
            while chunk := source.read(1024*1024):
                total += len(chunk)
                if total > 700*1024*1024:
                    raise ValueError('Dependency exceeds the 700 MiB limit')
                output.write(chunk)
        if total == 0:
            raise ValueError('Empty dependency')
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


if __name__ == '__main__':
    print(cache(sys.argv[1], sys.argv[2]))
