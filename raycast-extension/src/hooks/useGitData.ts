import { useState, useEffect } from "react";
import { runPythonScript } from "../utils/shell";
import { showToast, Toast } from "@raycast/api";

export interface GitData {
  currentBranch: string;
  remoteBranches: string[];
  contributors: string[];
  suggestedTickets: string[];
  suggestedTitle: string;
}

export function useGitData(repoPath?: string) {
  const [data, setData] = useState<GitData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      if (!repoPath) {
        setIsLoading(false);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const result = await runPythonScript(["--get-data"], repoPath);
        if (result.error) {
          setError(result.error);
        } else {
          setData(result);
        }
      } catch (error) {
        setError(String(error));
        showToast({
          style: Toast.Style.Failure,
          title: "Failed to fetch git data",
          message: String(error),
        });
      } finally {
        setIsLoading(false);
      }
    }
    fetchData();
  }, [repoPath]);

  return { data, isLoading, error };
}
