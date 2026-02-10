import {
  Form,
  ActionPanel,
  Action,
  showToast,
  Toast,
  Detail,
  open,
  getPreferenceValues,
  LocalStorage,
  List,
  Icon,
} from "@raycast/api";
import { useState, useEffect, useMemo, useRef } from "react";
import fs from "fs";
import path from "path";
import { useGitData } from "./hooks/useGitData";
import { runPythonScript } from "./utils/shell";

interface Preferences {
  projectsDirectory: string;
}

const REPO_PATH_KEY = "selected_repo_path";

function useRepos() {
  const [preferences, setPreferences] = useState<Preferences | null>(null);

  useEffect(() => {
    try {
      const prefs = getPreferenceValues<Preferences>();
      setPreferences(prefs);
    } catch (e) {
      console.error("Failed to load preferences:", e);
    }
  }, []);

  return useMemo(() => {
    if (!preferences?.projectsDirectory) return [];

    const baseDir = preferences.projectsDirectory.replace("~", process.env.HOME || "");

    try {
      if (!fs.existsSync(baseDir)) return [];

      return fs
        .readdirSync(baseDir)
        .filter((file) => {
          const fullPath = path.join(baseDir, file);
          try {
            return fs.statSync(fullPath).isDirectory() && fs.existsSync(path.join(fullPath, ".git"));
          } catch (e) {
            return false;
          }
        })
        .map((file) => ({
          name: file,
          path: path.join(baseDir, file),
        }));
    } catch (e) {
      console.error("Failed to read repositories:", e);
      return [];
    }
  }, [preferences?.projectsDirectory]);
}

export default function Command() {
  const repos = useRepos();
  const [selectedRepoPath, setSelectedRepoPath] = useState<string | null>(null);
  const [isChangingRepo, setIsChangingRepo] = useState(false);
  const { data, isLoading, error } = useGitData(selectedRepoPath || undefined);

  // Form States
  const [sourceBranch, setSourceBranch] = useState("");
  const [targetBranches, setTargetBranches] = useState<string[]>([]);
  const [jiraDetails, setJiraDetails] = useState("");
  const [titleExtension, setTitleExtension] = useState("");
  const [description, setDescription] = useState("");
  const [reviewers, setReviewers] = useState<string[]>([]);

  // Search states for dynamic "Add" items
  const [targetSearchText, setTargetSearchText] = useState("");
  const [reviewerSearchText, setReviewerSearchText] = useState("");

  // Preview States
  const [preview, setPreview] = useState<{ title: string; body: string } | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Ensure current branch is in the source options
  const allSourceOptions = useMemo(() => {
    const branches = [...(data?.remoteBranches || [])];
    if (data?.currentBranch && !branches.includes(data.currentBranch)) {
      branches.unshift(data.currentBranch);
    }
    return branches;
  }, [data?.remoteBranches, data?.currentBranch]);

  // Combine fetched remote branches with any custom ones user added
  const allTargetOptions = Array.from(new Set([...(data?.remoteBranches || []), ...targetBranches]));
  // Combine fetched contributors with any custom reviewers user added
  const allReviewerOptions = Array.from(new Set([...(data?.contributors || []), ...reviewers]));

  // Tracks if user has manually edited description to avoid overwriting it
  const isDescriptionDirty = useRef(false);

  useEffect(() => {
    async function init() {
      const storedPath = await LocalStorage.getItem<string>(REPO_PATH_KEY);
      if (storedPath) {
        setSelectedRepoPath(storedPath);
      }
    }
    init();
  }, []);

  // Sync initial data when repo data is fetched
  useEffect(() => {
    if (data) {
      setSourceBranch(data.currentBranch);
      setJiraDetails((data.suggestedTickets || []).join("\n"));
      setTitleExtension(data.suggestedTitle || "");
      // Pick first remote branch as default target if none selected
      if (targetBranches.length === 0 && data.remoteBranches?.length > 0) {
        const defaultTarget =
          data.remoteBranches.find((b) => b === "main" || b === "master" || b === "develop") || data.remoteBranches[0];
        setTargetBranches([defaultTarget]);
      }
    }
  }, [data]);

  // Fetch initial description when branches are set
  useEffect(() => {
    if (selectedRepoPath && sourceBranch && targetBranches.length > 0 && !isDescriptionDirty.current) {
      fetchInitialDescription();
    }
  }, [selectedRepoPath, sourceBranch, targetBranches]);

  async function fetchInitialDescription() {
    if (!selectedRepoPath) return;
    try {
      const result = await runPythonScript(
        ["--get-description", "--source", sourceBranch, "--target", targetBranches[0]],
        selectedRepoPath
      );
      if (result.description) {
        setDescription(result.description);
      }
    } catch (e) {
      console.error("Failed to fetch initial description:", e);
    }
  }

  // Automatic Preview Update (Debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (selectedRepoPath && sourceBranch && targetBranches.length > 0) {
        updatePreview();
      }
    }, 500);
    return () => clearTimeout(timer);
  }, [selectedRepoPath, sourceBranch, targetBranches, jiraDetails, titleExtension, description]);

  async function updatePreview() {
    if (!selectedRepoPath) return;
    setIsRefreshing(true);
    try {
      const jiraItems = jiraDetails
        .split(/[\n,]/)
        .map((s) => s.trim())
        .filter(Boolean);
      const args = ["--get-preview", "--source", sourceBranch];
      targetBranches.forEach((t) => {
        args.push("--target");
        args.push(t);
      });
      jiraItems.forEach((j) => {
        args.push("--tickets");
        args.push(j);
      });
      if (titleExtension) {
        args.push("--title");
        args.push(titleExtension);
      }
      if (description) {
        args.push("--body");
        args.push(description);
      }

      const result = await runPythonScript(args, selectedRepoPath);
      setPreview(result);
    } catch (e) {
      console.error("Preview failed:", e);
    } finally {
      setIsRefreshing(false);
    }
  }

  async function handleRepoSelect(repoPath: string) {
    await LocalStorage.setItem(REPO_PATH_KEY, repoPath);
    setSelectedRepoPath(repoPath);
    setIsChangingRepo(false);
    setPreview(null);
    isDescriptionDirty.current = false;
  }

  async function handleSubmit(values: any) {
    if (!values.targets || values.targets.length === 0) {
      await showToast({
        style: Toast.Style.Failure,
        title: "Target branch is required",
      });
      return;
    }

    const toast = await showToast({
      style: Toast.Style.Animated,
      title: "Creating Pull Request(s)...",
    });

    try {
      const args: string[] = ["--headless"];
      args.push("--source", values.source);
      values.targets.forEach((t: string) => {
        args.push("--target");
        args.push(t);
      });
      if (values.titleExtension) {
        args.push("--title");
        args.push(values.titleExtension);
      }
      if (values.description) {
        args.push("--body");
        args.push(values.description);
      }

      const tickets = values.jiraDetails
        .split(/[\n,]/)
        .map((s: string) => s.trim())
        .filter(Boolean);
      tickets.forEach((item: string) => {
        args.push("--tickets");
        args.push(item);
      });

      if (values.reviewers) {
        values.reviewers.forEach((r: string) => {
          args.push("--reviewers");
          args.push(r);
        });
      }

      const result = await runPythonScript(args, selectedRepoPath || undefined);

      if (result.success) {
        const successResults = result.results.filter((r: any) => r.url);
        const skippedResults = result.results.filter((r: any) => r.skipped);
        const failedResults = result.results.filter((r: any) => r.error);

        if (successResults.length > 0) {
          toast.style = Toast.Style.Success;
          toast.title = "PR(s) created successfully!";
          toast.message = `Created ${successResults.length} PR(s)`;
          successResults.forEach((r: any) => {
            open(r.url);
          });

          toast.primaryAction = {
            title: "Open PRs",
            onAction: () => {
              successResults.forEach((r: any) => {
                open(r.url);
              });
            },
          };

          setSourceBranch(data?.currentBranch || "");
          setTargetBranches([]);
          setJiraDetails("");
          setTitleExtension("");
          setDescription("");
          setReviewers([]);
          setPreview(null);
          isDescriptionDirty.current = false;
        } else if (failedResults.length > 0) {
          toast.style = Toast.Style.Failure;
          toast.title = "Failed to create PR";
          toast.message = failedResults.map((r: any) => `${r.target}: ${r.error}`).join("\n");
        } else if (skippedResults.length > 0) {
          toast.style = Toast.Style.Success;
          toast.title = "Action Complete";
          toast.message = skippedResults.map((r: any) => `${r.target}: ${r.reason}`).join("\n");
        } else {
          toast.style = Toast.Style.Success;
          toast.title = "Done";
          toast.message = "No new PRs were needed.";
        }
      } else {
        throw new Error(result.error || "Unknown error");
      }
    } catch (error) {
      toast.style = Toast.Style.Failure;
      toast.title = "Failed to create PR";
      toast.message = String(error);
    }
  }

  if (!selectedRepoPath || isChangingRepo) {
    return <SelectRepo onSelect={handleRepoSelect} />;
  }

  // Show loading during fetch or when transition state causes data/error gap
  if (isLoading || (!data && !error)) {
    return <Detail isLoading={true} />;
  }

  if (error || (data as any)?.error) {
    return (
      <Detail
        markdown={`# Error\n${error || (data as any)?.error || "Failed to load git data."}`}
        actions={
          <ActionPanel>
            <Action title="Change Repository" onAction={() => setIsChangingRepo(true)} />
          </ActionPanel>
        }
      />
    );
  }

  if (!data) return null;

  if (!data) return null;

  return (
    <Form
      isLoading={isRefreshing}
      actions={
        <ActionPanel>
          <Action.SubmitForm title="Create Pull Request" onSubmit={handleSubmit} />
          <Action
            title="Change Repository"
            icon={Icon.Switch}
            onAction={() => setIsChangingRepo(true)}
            shortcut={{ modifiers: ["cmd"], key: "r" }}
          />
          <Action
            title="Refresh Preview"
            icon={Icon.ArrowClockwise}
            onAction={updatePreview}
            shortcut={{ modifiers: ["cmd"], key: "u" }}
          />
        </ActionPanel>
      }
    >
      <Form.Dropdown id="repository" title="Repository" value={selectedRepoPath || ""} onChange={handleRepoSelect}>
        {repos.map((r) => (
          <Form.Dropdown.Item key={r.path} value={r.path} title={r.name} />
        ))}
      </Form.Dropdown>

      <Form.Dropdown id="source" title="Source Branch" value={sourceBranch} onChange={setSourceBranch}>
        {allSourceOptions.map((b) => (
          <Form.Dropdown.Item key={b} value={b} title={b === data.currentBranch ? `${b} (Current)` : b} />
        ))}
      </Form.Dropdown>

      <Form.TagPicker
        id="targets"
        title="Target Branches"
        placeholder="Select or type target(s)"
        value={targetBranches}
        onChange={setTargetBranches}
        // @ts-expect-error onSearchTextChange exists in runtime for TagPicker
        onSearchTextChange={setTargetSearchText}
      >
        {allTargetOptions.map((b) => (
          <Form.TagPicker.Item key={b} value={b} title={b} />
        ))}
        {targetSearchText && !allTargetOptions.includes(targetSearchText) && (
          <Form.TagPicker.Item key="__add_target" value={targetSearchText} title={`Add "${targetSearchText}"`} />
        )}
      </Form.TagPicker>

      <Form.Description
        title="Title Pattern (Default)"
        text={
          sourceBranch && targetBranches.length > 0
            ? `\`[TICKET][TITLE][${sourceBranch}] -> [${targetBranches[0] || "target"}]\``
            : "Select branches to see the pattern"
        }
      />

      <Form.Separator />

      <Form.TextArea
        id="jiraDetails"
        title="JIRA Details"
        placeholder="Enter Ticket ID or URL (one per line)"
        value={jiraDetails}
        onChange={setJiraDetails}
        info="Paste Ticket IDs or full JIRA URLs. One per line."
      />

      <Form.TextField
        id="titleExtension"
        title="Title Extension"
        placeholder="Descriptive part of the title"
        value={titleExtension}
        onChange={setTitleExtension}
      />

      <Form.TextArea
        id="description"
        title="Description"
        placeholder="Auto-generated from commits..."
        value={description}
        onChange={(val) => {
          isDescriptionDirty.current = true;
          setDescription(val);
        }}
      />

      <Form.TagPicker
        id="reviewers"
        title="Reviewers"
        placeholder="Select or type username"
        value={reviewers}
        onChange={setReviewers}
        // @ts-expect-error onSearchTextChange exists in runtime for TagPicker
        onSearchTextChange={setReviewerSearchText}
      >
        {allReviewerOptions.map((c) => (
          <Form.TagPicker.Item key={c} value={c} title={c} />
        ))}
        {reviewerSearchText && !allReviewerOptions.includes(reviewerSearchText) && (
          <Form.TagPicker.Item key="__add_reviewer" value={reviewerSearchText} title={`Add "${reviewerSearchText}"`} />
        )}
      </Form.TagPicker>

      {preview && (
        <>
          <Form.Separator />
          <Form.Description
            title="Final PR Preview"
            text={`**Full Title:** \`${preview.title}\`\n\n**Full Description:**\n\n${preview.body}`}
          />
        </>
      )}
    </Form>
  );
}

function SelectRepo({ onSelect }: { onSelect: (path: string) => void }) {
  const preferences = getPreferenceValues<Preferences>();
  const repos = useRepos();

  if (repos.length === 0) {
    return (
      <Detail
        markdown={`# No Repositories Found\n\nPlease check your **Projects Directory** in extension preferences.\n\nCurrent path: \`${preferences.projectsDirectory}\`\n\nEnsure this directory exists and contains git repositories.`}
      />
    );
  }

  return (
    <List searchBarPlaceholder="Search repositories...">
      {repos.map((repo) => (
        <List.Item
          key={repo.path}
          title={repo.name}
          subtitle={repo.path}
          icon={Icon.Folder}
          actions={
            <ActionPanel>
              <Action title="Select Repository" onAction={() => onSelect(repo.path)} />
            </ActionPanel>
          }
        />
      ))}
    </List>
  );
}
