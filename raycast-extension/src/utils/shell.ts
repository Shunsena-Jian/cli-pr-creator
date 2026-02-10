import { execFile } from "child_process";
import path from "path";
import { promisify } from "util";
import { environment } from "@raycast/api";

const execFileAsync = promisify(execFile);

export async function runPythonScript(
  args: string[],
  cwd?: string,
): Promise<any> {
  const scriptPath = path.join(environment.assetsPath, "pr_engine.py");

  const finalArgs = [...args];
  if (cwd) {
    finalArgs.push(cwd);
  }

  try {
    const { stdout, stderr } = await execFileAsync(
      "python3",
      [scriptPath, ...finalArgs],
      {
        cwd,
        env: {
          ...process.env,
          PATH: `/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${process.env.PATH}`,
        },
        maxBuffer: 10 * 1024 * 1024,
      },
    );
    if (stderr && !stdout) {
      console.warn("Python stderr:", stderr);
    }
    return JSON.parse(stdout);
  } catch (error: any) {
    console.error("Python Execution Error:", error);
    // Attempt to parse JSON from stdout even if it failed (it might have printed error JSON)
    if (error.stdout) {
      try {
        return JSON.parse(error.stdout);
      } catch (e) {
        // ignore
      }
    }
    throw error;
  }
}
