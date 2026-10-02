"""Execute the real release workflow JavaScript against isolated in-memory APIs.

Run with python -m unittest discover -s tests -p test_release_runtime.py -v.
Node.js is required. No GitHub requests, archive extraction or file writes occur.
"""

import json
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def release_script():
    workflow = (ROOT / ".github/workflows/publish-release.yml").read_text()
    _, marker, remainder = workflow.partition("          script: |\n")
    if not marker:
        raise AssertionError("Release workflow JavaScript block not found")
    lines = []
    for line in remainder.splitlines():
        if line.strip() and not line.startswith("            "):
            break
        lines.append(line)
    return textwrap.dedent("\n".join(lines))


# Only external effects are replaced. Decisions, checksums, provenance and release
# publication logic execute unchanged from publish-release.yml.
HARNESS = r"""
const nativeRequire = require;
const {createHash} = require('crypto');
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const {script, mode} = input;
const sha = 'a'.repeat(40);
const otherSha = 'b'.repeat(40);
const repo = {owner: 'example', repo: 'sideband'};
const windowsName = 'Sideband_1.9.2_windows_x86_64.zip';
const refsChecked = [];
const uploads = [];
const deletions = [];
const logs = [];
let headReads = 0;
let nextAssetId = 100;
let publicationCalls = 0;
let release = {id: 9, draft: true, html_url: 'https://example.invalid/releases/9'};
let saved = mode === 'empty-starter'
  ? [{id: 8, name: windowsName, size: 0, state: 'starter'}]
  : mode === 'unexpected-extra'
    ? [{id: 8, name: 'unexpected.exe', size: 10, state: 'uploaded'}]
    : [];

const runs = ['build-windows-zip.yml', 'build-android-apk.yml', 'build-desktop.yml']
  .map((name, i) => ({
    id: i + 1, name, head_sha: sha, status: 'completed', conclusion: 'success',
    head_repository: {full_name: 'example/sideband'},
    html_url: `https://example.invalid/runs/${i + 1}`
  }));
const artifacts = {
  1: [{id: 10, name: 'sideband-windows-zip-1', expired: false}],
  2: [{id: 20, name: 'sideband-android-apk-1', expired: false}],
  3: [
    {id: 30, name: 'sideband-desktop-linux-x86_64-1', expired: false},
    {id: 31, name: 'sideband-desktop-macos-arm64-1', expired: false},
    {id: 32, name: 'sideband-desktop-macos-x86_64-1', expired: false}
  ]
};
const files = {
  10: [windowsName],
  20: ['sideband-1.9.2-arm64-v8a-test-signed.apk', 'APK-SIGNATURE.txt'],
  30: ['Sideband-1.9.2-x86_64.AppImage'],
  31: ['Sideband-zh-CN-macos-arm64.dmg'],
  32: ['Sideband-zh-CN-macos-x86_64.dmg']
};
const fakeFs = {
  mkdirSync() {},
  writeFileSync() {},
  readdirSync(directory) {
    const id = directory.split('/').pop();
    if (!files[id]) throw new Error(`Unexpected artifact directory: ${directory}`);
    return files[id].map(name => ({
      name, isSymbolicLink: () => false, isDirectory: () => false,
      isFile: () => true
    }));
  },
  readFileSync(filename) {
    return Buffer.from(filename.endsWith('APK-SIGNATURE.txt')
      ? (mode === 'unsigned' ? 'unsigned, not installable\n' : 'sideband-1.9.2-arm64-v8a-test-signed.apk: TEST SIGNATURE ONLY; signature verified\n')
      : `fixture bytes for ${filename.split('/').pop()}`);
  }
};
function isolatedRequire(name) {
  if (name === 'fs') return fakeFs;
  if (name === 'child_process') return {
    execFileSync(command) {
      if (command !== 'unzip') throw new Error(`Unexpected executable: ${command}`);
    }
  };
  if (name === 'path' || name === 'crypto') return nativeRequire(name);
  throw new Error(`Unmocked dependency: ${name}`);
}
const actions = {
  listWorkflowRunArtifacts() {},
  async listWorkflowRuns({workflow_id}) {
    return {data: {workflow_runs: runs.filter(run => run.name === workflow_id)}};
  },
  async downloadArtifact() { return {data: Buffer.from('mock archive')}; }
};
const repos = {
  listReleaseAssets() {},
  async getContent() {
    return {data: {content: Buffer.from('__version__ = "1.9.2"').toString('base64')}};
  },
  async getReleaseByTag() {
    if (['existing-wrong-tag', 'empty-starter', 'unexpected-extra'].includes(mode)) {
      return {data: {...release}};
    }
    throw Object.assign(new Error('No release yet'), {status: 404});
  },
  async createRelease(values) {
    release = {...release, ...values};
    return {data: {...release}};
  },
  async uploadReleaseAsset({name, data}) {
    uploads.push(name);
    const asset = {
      id: nextAssetId++, name, size: data.length, state: 'uploaded',
      digest: 'sha256:' + createHash('sha256').update(data).digest('hex')
    };
    if (mode === 'bad-upload') asset.digest = 'sha256:' + '0'.repeat(64);
    saved.push(asset);
    return {data: {...asset}};
  },
  async deleteReleaseAsset({asset_id}) {
    deletions.push(asset_id);
    saved = saved.filter(asset => asset.id !== asset_id);
    return {};
  },
  async updateRelease(values) {
    if (values.draft === false) publicationCalls++;
    release = {...release, ...values};
    return {data: {...release}};
  }
};
const git = {
  async getRef({ref}) {
    refsChecked.push(ref);
    let value = sha;
    if (ref === 'heads/main' && ++headReads > 1 && mode === 'main-advanced') {
      value = otherSha;
    }
    if (ref.startsWith('tags/') && mode === 'existing-wrong-tag') value = otherSha;
    return {data: {object: {sha: value}}};
  },
  async createRef() { return {data: {}}; }
};
const github = {
  rest: {actions, repos, git},
  async paginate(method, args) {
    if (method === actions.listWorkflowRunArtifacts) return artifacts[args.run_id];
    if (method === repos.listReleaseAssets) return saved.map(asset => ({...asset}));
    throw new Error('Unmocked pagination endpoint');
  }
};
const core = {
  info(message) { logs.push(message); },
  summary: {addLink() {}, async write() {}}
};
(async () => {
  let error = null;
  try {
    await new Function('require', 'github', 'context', 'core', 'process',
      'return (async () => {\n' + script + '\n})()')(
        isolatedRequire, github, {repo, payload: {workflow_run: {head_sha: sha}}},
        core, {env: {RUNNER_TEMP: '/fake-runner'}});
  } catch (caught) { error = caught.message; }
  process.stdout.write(JSON.stringify({
    error, release, publicationCalls, refsChecked, uploads, deletions, logs,
    assets: saved
  }));
})();
"""


@unittest.skipUnless(NODE, "Node.js is required for release workflow runtime tests")
class ReleaseRuntimeTests(unittest.TestCase):
    def run_scenario(self, mode):
        result = subprocess.run(
            [NODE, "-e", HARNESS],
            input=json.dumps({"script": release_script(), "mode": mode}),
            capture_output=True, text=True, check=True, timeout=15,
        )
        return json.loads(result.stdout)

    def test_unsigned_android_cannot_be_published_as_this_test_release(self):
        result = self.run_scenario("unsigned")
        self.assertIn("installable test-signed", result["error"] or "")
        self.assertEqual(result["publicationCalls"], 0)
        self.assertEqual(result["uploads"], [])

    def test_success_publishes_verified_assets_and_provenance(self):
        result = self.run_scenario("normal")
        self.assertIsNone(result["error"])
        self.assertEqual(result["publicationCalls"], 1)
        self.assertFalse(result["release"]["draft"])
        self.assertTrue(result["release"]["prerelease"])
        self.assertIn("SHA256SUMS", result["uploads"])
        self.assertIn("BUILD-PROVENANCE.json", result["uploads"])
        self.assertEqual(len(result["assets"]), 8)

    def test_new_main_commit_during_upload_leaves_release_draft(self):
        result = self.run_scenario("main-advanced")
        self.assertIsNone(result["error"])
        self.assertTrue(result["uploads"], "Main must advance after uploads start")
        self.assertEqual(result["publicationCalls"], 0)
        self.assertTrue(result["release"]["draft"])

    def test_existing_release_with_wrong_tag_sha_is_not_modified(self):
        result = self.run_scenario("existing-wrong-tag")
        self.assertIn("different commit", result["error"] or "")
        self.assertEqual(result["uploads"], [])
        self.assertEqual(result["deletions"], [])
        self.assertEqual(result["publicationCalls"], 0)

    def test_uploaded_digest_mismatch_blocks_publication(self):
        result = self.run_scenario("bad-upload")
        self.assertIn("verification failed", result["error"] or "")
        self.assertTrue(result["uploads"])
        self.assertEqual(result["publicationCalls"], 0)
        self.assertTrue(result["release"]["draft"])

    def test_empty_starter_asset_can_be_retried_in_draft(self):
        result = self.run_scenario("empty-starter")
        self.assertIsNone(result["error"])
        self.assertEqual(result["deletions"], [8])
        self.assertEqual(result["publicationCalls"], 1)
        self.assertEqual(len(result["assets"]), 8)
        self.assertTrue(all(asset["state"] == "uploaded" for asset in result["assets"]))

    def test_unexpected_existing_asset_blocks_publication(self):
        result = self.run_scenario("unexpected-extra")
        self.assertIn("Unexpected release asset count", result["error"] or "")
        self.assertEqual(result["publicationCalls"], 0)
        self.assertTrue(result["release"]["draft"])
        self.assertEqual(result["deletions"], [])


if __name__ == "__main__":
    unittest.main()
