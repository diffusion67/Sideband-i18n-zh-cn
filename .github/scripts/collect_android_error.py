"""Keep bounded compiler diagnostics without uploading the build environment."""
import re
import sys
from pathlib import Path


def excerpt(text):
    # Logs are downloaded to a file, never rendered as terminal control data.
    text = re.sub(r'\x1b\].*?(?:\x07|\x1b\\)', '', text, flags=re.S)
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = re.sub(r'[\x00-\x08\x0b-\x1f\x7f]', '', text)
    text = text.split('# ENVIRONMENT:', 1)[0]
    # p4a emits a separate shell environment dump before its command summary.
    text = re.sub(r'^\[INFO\]:\s*ENV:\n.*?(?=^\[INFO\]:\s*COMMAND:|\Z)',
                  '[build environment omitted]\n', text, flags=re.M | re.S)
    lines = []
    private_key = False
    for line in text.splitlines():
        if '-----BEGIN ' in line and 'PRIVATE KEY-----' in line:
            private_key = True
        if private_key:
            if '-----END ' in line and 'PRIVATE KEY-----' in line:
                private_key = False
            continue
        if re.search(r'token|password|passwd|secret|authorization|extraheader|private.?key', line, re.I):
            lines.append('[redacted sensitive-looking diagnostic line]')
        else:
            lines.append(re.sub(r'(https?://)[^/\s@]+@', r'\1[redacted]@', line))
    return '\n'.join(lines[-2000:]) + '\n'


if __name__ == '__main__':
    Path(sys.argv[2]).write_text(excerpt(Path(sys.argv[1]).read_text(errors='replace')), encoding='utf-8')
