import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createRoleResourceLoader } from "../src/novel_role_resources.mjs";


const resourcesRoot = fileURLToPath(new URL("../resources/roles", import.meta.url));


test("writer loader uses built-in role prompt and core skill", () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), "awp-role-resources-"));
  try {
    const loader = createRoleResourceLoader("writer", resourcesRoot, projectRoot);
    const skills = loader.getSkills().skills;

    assert.match(loader.getSystemPrompt(), /Writer/i);
    assert(skills.some((skill) => skill.name === "writer-core"));
    assert.equal(loader.getExtensions().extensions.length, 0);
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});


test("loader includes project agent skills but ignores project dot-pi", () => {
  const projectRoot = fs.mkdtempSync(path.join(os.tmpdir(), "awp-role-project-"));
  try {
    const allowed = path.join(projectRoot, "agent", "skills", "project-style");
    const forbidden = path.join(projectRoot, ".pi", "skills", "global-style");
    fs.mkdirSync(allowed, { recursive: true });
    fs.mkdirSync(forbidden, { recursive: true });
    fs.writeFileSync(path.join(allowed, "SKILL.md"), "---\nname: project-style\ndescription: allowed\n---\nUse project style.\n");
    fs.writeFileSync(path.join(forbidden, "SKILL.md"), "---\nname: global-style\ndescription: forbidden\n---\nDo not load.\n");

    const loader = createRoleResourceLoader("writer", resourcesRoot, projectRoot);
    const names = loader.getSkills().skills.map((skill) => skill.name);

    assert(names.includes("project-style"));
    assert(!names.includes("global-style"));
  } finally {
    fs.rmSync(projectRoot, { recursive: true, force: true });
  }
});


test("loader rejects unknown role", () => {
  assert.throws(
    () => createRoleResourceLoader("shell", resourcesRoot, process.cwd()),
    /unsupported Pi novel role/,
  );
});

