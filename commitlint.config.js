module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    "subject-case": [0],
    "body-max-line-length": [2, "always", 200],
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "chore",
        "refactor",
        "test",
        "revert",
      ],
    ],
    "scope-enum": [0],
    "scope-empty": [0],
  },
};
