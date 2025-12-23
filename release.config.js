module.exports = {
  branches: [
    "main",
    { name: "feat/*", prerelease: true },
    { name: "fix/*", prerelease: true },
  ],
  plugins: [
    "@semantic-release/commit-analyzer",
    "@semantic-release/release-notes-generator",
    "@semantic-release/github",
    [
      "@semantic-release/exec",
      {
        prepareCmd: "./scripts/bump_version.sh ${nextRelease.version}",
      },
    ],
  ],
};
