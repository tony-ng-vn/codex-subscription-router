const CODEX_MUX_API = "http://127.0.0.1:__CODEX_MUX_CONTROL_PORT__/v1";
const CODEX_MUX_TOKEN = "__CODEX_MUX_CONTROL_TOKEN__";
let codexMuxLoginActive = false;

function CodexMuxProfileMenuOpenChange(setOpen) {
  return (nextOpen) => {
    if (!nextOpen && codexMuxLoginActive) return;
    setOpen(nextOpen);
  };
}

async function codexMuxRequest(path, options = {}) {
  const response = await fetch(`${CODEX_MUX_API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Codex-Mux-Token": CODEX_MUX_TOKEN,
      ...options.headers,
    },
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed (${response.status})`);
  return body;
}

const CODEX_MUX_ACCOUNT_SCOPED_PLUGIN_METHODS = new Set([
  "list-apps",
  "list-installed-apps",
  "read-apps",
  "list-mcp-server-status",
  "login-mcp-server",
  "app/list",
  "app/installed",
  "app/read",
  "mcpServerStatus/list",
  "mcpServer/oauth/login",
]);

function codexMuxScopePluginRequest(method, params) {
  const accountId = globalThis.__codexMuxPluginAccountId;
  if (
    !accountId ||
    !CODEX_MUX_ACCOUNT_SCOPED_PLUGIN_METHODS.has(method) ||
    (params != null &&
      (typeof params !== "object" || Array.isArray(params)))
  ) {
    return params;
  }
  return { ...(params || {}), codexMuxAccountId: accountId };
}

async function codexMuxProfileData(accountId = null) {
  const query = accountId
    ? `?accountId=${encodeURIComponent(accountId)}`
    : "";
  const result = await codexMuxRequest(`/profile/combined${query}`);
  globalThis.__codexMuxCombinedProfileAccounts = result.accounts || [];
  return result.profile;
}

async function codexMuxRateLimitResets(accountId) {
  return codexMuxRequest(
    `/accounts/${encodeURIComponent(accountId)}/rate-limit-resets`,
  );
}

async function codexMuxPreferAccount(accountId) {
  return codexMuxRequest(`/accounts/${encodeURIComponent(accountId)}/prefer`, {
    method: "POST",
    body: "{}",
  });
}

async function codexMuxConsumeRateLimitReset(accountId, input) {
  return codexMuxRequest(
    `/accounts/${encodeURIComponent(accountId)}/rate-limit-resets/consume`,
    {
      method: "POST",
      body: JSON.stringify({
        creditId: input.creditId ?? null,
        redeemRequestId: input.redeemRequestId,
      }),
    },
  );
}

function CodexMuxUsageModal({
  accountId,
  onClose,
  onResetComplete,
}) {
  globalThis.__codexMuxInitialResetAccountId = accountId;
  return (0, e7.jsx)(QLs, {
    defaultResetCreditsOpen: true,
    initialAvailableCount: 0,
    isRateLimitReached: false,
    onClose: () => {
      delete globalThis.__codexMuxInitialResetAccountId;
      onClose?.();
    },
    onResetComplete: () => onResetComplete?.(),
  });
}

function CodexMuxUseResetAccountState() {
  const cachedAccounts = (globalThis.__codexMuxConnectedAccounts || []).filter(
    (account) => account.connected && account.enabled,
  );
  const [accounts, setAccounts] = kXc.useState(cachedAccounts);
  const [selectedId, setSelectedId] = kXc.useState(
    globalThis.__codexMuxInitialResetAccountId || "primary",
  );
  const [resetSummaries, setResetSummaries] = kXc.useState({});
  const [loading, setLoading] = kXc.useState(cachedAccounts.length === 0);

  const loadAccounts = kXc.useCallback(async () => {
    const result = await codexMuxRequest("/accounts");
    const connected = (result.accounts || []).filter(
      (account) => account.connected && account.enabled,
    );
    setAccounts(connected);
    setSelectedId((current) =>
      connected.some((account) => account.id === current)
        ? current
        : connected[0]?.id || "primary",
    );
    setLoading(false);
    const entries = await Promise.all(
      connected.map(async (account) => {
        try {
          const resets = await codexMuxRateLimitResets(account.id);
          return [account.id, Math.max(0, resets.available_count || 0)];
        } catch {
          return [account.id, null];
        }
      }),
    );
    setResetCounts(Object.fromEntries(entries));
  }, []);

  kXc.useEffect(() => {
    loadAccounts().catch(() => setLoading(false));
  }, [loadAccounts]);

  kXc.useEffect(
    () => () => {
      delete window.__codexMuxResetAccountId;
      delete window.__codexMuxSelectedUsageWindows;
      delete window.__codexMuxResetAccountSelector;
      delete window.__codexMuxInitialResetAccountId;
    },
    [],
  );

  const selected =
    accounts.find((account) => account.id === selectedId) || accounts[0] || null;
  const activeId = selected?.id || selectedId;
  window.__codexMuxResetAccountId = activeId;
  window.__codexMuxSelectedUsageWindows = selected
    ? codexMuxUsageWindows(selected.rateLimits)
    : null;
  window.__codexMuxResetAccountSelector = (0, e7.jsx)(
    CodexMuxResetAccountTarget,
    {
      loading,
      account: selected,
      resetCount: resetCounts[activeId],
    },
  );

}

function CodexMuxResetAccountTarget({
  account,
  loading,
  resetCount,
}) {
  return (0, e7.jsxs)("div", {
    className: "pt-4",
    children: [
      (0, e7.jsx)("div", {
        className:
          "mb-2 px-1 text-xs font-medium text-token-text-secondary",
        children: "Apply this reset to",
      }),
      (0, e7.jsx)("div", {
        className:
          "rounded-2xl border border-token-border p-2",
        children: loading
          ? (0, e7.jsx)("div", {
              className: "px-2 py-2 text-sm text-token-text-secondary",
              children: "Loading subscription...",
            })
          : account
            ? (0, e7.jsxs)("div", {
                className: "flex items-center gap-2 rounded-xl px-3 py-2",
                children: [
                  (0, e7.jsx)(CodexMuxAccountAvatar, {
                    imageUrl: account.profileImageUrl,
                    label: account.label,
                    className: "size-7",
                  }),
                  (0, e7.jsxs)("span", {
                    className: "flex min-w-0 flex-col",
                    children: [
                      (0, e7.jsx)("span", {
                        className: "max-w-52 truncate text-sm font-medium",
                        children: account.planLabel
                          ? `${account.label} - ${account.planLabel}`
                          : account.label,
                      }),
                      (0, e7.jsx)("span", {
                        className: "text-xs text-token-text-tertiary",
                        children:
                          resetCount == null
                            ? "Reset status unavailable"
                            : resetCount === 1
                              ? "1 reset available for this subscription"
                              : `${resetCount} resets available for this subscription`,
                      }),
                    ],
                  }),
                ],
              })
            : null,
      }),
    ],
  });
}

function CodexMuxAccountMenu() {
  const modalScope = Lo(Q);
  const [accounts, setAccounts] = kXc.useState([]);
  const [resetCounts, setResetCounts] = kXc.useState({});
  const [loading, setLoading] = kXc.useState(true);
  const [busy, setBusy] = kXc.useState(false);
  const [error, setError] = kXc.useState("");
  const [login, setLogin] = kXc.useState(null);
  const [codeCopied, setCodeCopied] = kXc.useState(false);
  const resetSummariesLoadedAt = kXc.useRef(0);
  const loginAccountId = login?.accountId || null;

  const refresh = kXc.useCallback(async (forceResetSummaries = false) => {
    try {
      const result = await codexMuxRequest("/accounts");
      const nextAccounts = result.accounts || [];
      globalThis.__codexMuxConnectedAccounts = nextAccounts.filter(
        (account) => account.connected && account.enabled,
      );
      setAccounts(nextAccounts);
      const resetSummariesAreStale =
        Date.now() - resetSummariesLoadedAt.current >= 5 * 60 * 1_000;
      if (forceResetSummaries || resetSummariesAreStale) {
        const resetEntries = await Promise.all(
          globalThis.__codexMuxConnectedAccounts.map(async (account) => {
            try {
              const resets = await codexMuxRateLimitResets(account.id);
              return [account.id, codexMuxResetSummary(resets)];
            } catch {
              return [account.id, { count: null, expiresAt: null }];
            }
          }),
        );
        setResetSummaries(Object.fromEntries(resetEntries));
        resetSummariesLoadedAt.current = Date.now();
      }
      setError("");
      if (nextAccounts.some((account) => account.connected)) setLoading(false);
    } catch (requestError) {
      setError(requestError.message);
      setLoading(false);
    }
  }, []);

  kXc.useEffect(() => {
    refresh();
    const events = new EventSource(
      `${CODEX_MUX_API}/events?token=${encodeURIComponent(CODEX_MUX_TOKEN)}`,
    );
    events.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (
          payload.type === "account-updated" &&
          payload.accountId === loginAccountId
        ) {
          codexMuxLoginActive = false;
          setLogin(null);
        }
        if (payload.type === "account-updated") refresh();
      } catch {}
    };
    const warmupTimer = setTimeout(refresh, 2_000);
    const loadingDeadline = setTimeout(() => {
      refresh().finally(() => setLoading(false));
    }, 6_000);
    const timer = setInterval(refresh, 30_000);
    return () => {
      clearTimeout(warmupTimer);
      clearTimeout(loadingDeadline);
      clearInterval(timer);
      events.close();
    };
  }, [refresh, loginAccountId]);

  kXc.useEffect(() => {
    if (!login) return;
    const allowEscapeDismissal = (event) => {
      if (event.key !== "Escape") return;
      codexMuxLoginActive = false;
      setLogin(null);
    };
    window.addEventListener("keydown", allowEscapeDismissal, true);
    return () => window.removeEventListener("keydown", allowEscapeDismissal, true);
  }, [login]);

  const connected = accounts.filter(
    (account) => account.connected && account.enabled,
  );
  const weeklyWindows = connected.map((account) =>
    codexMuxWeeklyWindow(account.rateLimits),
  );
  const hasCompleteUsage =
    connected.length > 0 && weeklyWindows.every((weekly) => weekly != null);
  const totalRemaining = weeklyWindows.reduce(
    (total, weekly) =>
      total + (weekly == null ? 0 : Math.max(0, 100 - weekly.usedPercent)),
    0,
  );

  async function addSubscription(event) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      const created = await codexMuxRequest("/accounts", {
        method: "POST",
        body: JSON.stringify({ label: `Subscription ${connected.length + 1}` }),
      });
      const result = await codexMuxRequest(`/accounts/${created.account.id}/login`, {
        method: "POST",
        body: JSON.stringify({ mode: "chatgptDeviceCode" }),
      });
      const pendingLogin = result.login
        ? { ...result.login, accountId: created.account.id }
        : null;
      codexMuxLoginActive = pendingLogin != null;
      setCodeCopied(false);
      setLogin(pendingLogin);
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  async function preferSubscription(event, accountId) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await codexMuxPreferAccount(accountId);
      await refresh();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  function openAccountReset(event, accountId) {
    event.preventDefault();
    BW(modalScope, CodexMuxUsageModal, {
      accountId,
      onResetComplete: () => refresh(true),
    });
  }

  async function copyCodeAndContinue(event) {
    event.preventDefault();
    const userCode = login?.userCode || "";
    const verificationUrl = login?.verificationUrl || login?.authUrl || "";
    const copy = userCode
      ? navigator.clipboard.writeText(userCode)
      : Promise.resolve();
    if (verificationUrl) {
      try {
        const destination = new URL(verificationUrl);
        const trustedHost =
          destination.hostname === "chatgpt.com" ||
          destination.hostname === "auth.openai.com";
        if (destination.protocol !== "https:" || !trustedHost) {
          throw new Error("untrusted verification URL");
        }
        window.open(destination.href, "_blank", "noopener,noreferrer");
      } catch {
        setError("The sign-in verification page could not be opened safely.");
      }
    }
    try {
      await copy;
      setCodeCopied(userCode !== "");
    } catch {
      setError("The sign-in code could not be copied.");
    }
  }

  const rows = [];
  rows.push(
    (0, e7.jsx)(
      _H,
      {
        LeftIcon: S2,
        SubText: loading
          ? "Connecting subscriptions..."
          : connected.length === 1
            ? "1 connected subscription"
            : `${connected.length} connected subscriptions`,
        rightIcon: (0, e7.jsx)("span", {
          className: "text-token-description-foreground tabular-nums",
          children: loading
            ? "..."
            : hasCompleteUsage
              ? `${Math.round(totalRemaining)}%`
              : "-",
        }),
        children: "Usage remaining",
      },
      "codex-mux-total",
    ),
  );
  if (connected.length > 0) {
    rows.push(
      (0, e7.jsx)(CH.Separator, {}, "codex-mux-accounts-separator"),
    );
  }

  for (const account of connected) {
    const weekly = codexMuxWeeklyWindow(account.rateLimits);
    const remaining = weekly == null ? null : Math.max(0, 100 - weekly.usedPercent);
    const identity = codexMuxAccountIdentity(account);
    const usageState = codexMuxUsageState(remaining);
    rows.push(
      (0, e7.jsx)(
        _H,
        {
          LeftIcon: (iconProps) =>
            (0, e7.jsx)(CodexMuxAccountAvatar, {
              ...iconProps,
              imageUrl: account.profileImageUrl,
              label: account.label,
            }),
          SubText: account.email
            ? (0, e7.jsx)(CodexMuxMaskedEmail, { email: account.email })
            : account.planType || "ChatGPT subscription",
          className: "group",
          onSelect: account.preferred
            ? undefined
            : (event) => preferSubscription(event, account.id),
          rightIcon: (0, e7.jsx)("span", {
            className: `${usageState.textClass} tabular-nums`,
            "aria-label": usageState.ariaLabel,
            children: remaining == null ? "-" : `${Math.round(remaining)}%`,
          }),
          children: [
            identity.name,
            ...identity.metadata,
            ...(account.preferred ? [] : ["Use now"]),
          ].join(" - "),
        },
        `codex-mux-account-${account.id}`,
      ),
    );
    const resetSummary = resetSummaries[account.id] || {
      count: null,
      expiresAt: null,
    };
    const resetTiming = codexMuxDateTiming(resetSummary.expiresAt);
    const resetTarget = account.planLabel
      ? `Applies only to ${account.label} - ${account.planLabel}`
      : `Applies only to ${account.label}`;
    rows.push(
      (0, e7.jsx)(
        _H,
        {
          LeftIcon: (iconProps) =>
            (0, e7.jsx)(CodexMuxResetCreditIcon, {
              ...iconProps,
              available: resetSummary.count > 0,
            }),
          SubText: resetTiming
            ? `${resetTarget} - Expires ${resetTiming.dateLabel}${
                resetTiming.relativeLabel
                  ? ` ${resetTiming.relativeLabel}`
                  : ""
              }`
            : resetTarget,
          onSelect:
            resetSummary.count > 0
              ? (event) => openAccountReset(event, account.id)
              : undefined,
          rightIcon:
            resetSummary.count > 0
              ? (0, e7.jsx)("span", {
                  className: resetTiming?.urgent
                    ? "text-warning font-medium"
                    : "text-chart-green font-medium",
                  children: "Apply",
                })
              : null,
          children: codexMuxResetCopy(resetSummary.count),
        },
        `codex-mux-reset-${account.id}`,
      ),
    );
  }

  if (login) {
    rows.push(
      (0, e7.jsx)(
        _H,
        {
          LeftIcon: CodexMuxCopyIcon,
          SubText: login.userCode
            ? codeCopied
              ? `Code ${login.userCode} copied`
              : `Code ${login.userCode} - Click to copy`
            : "Finish signing in with ChatGPT",
          onSelect: copyCodeAndContinue,
          children: "Continue sign-in",
        },
        "codex-mux-login",
      ),
    );
  }

  if (error) {
    rows.push(
      (0, e7.jsx)(
        _H,
        {
          LeftIcon: S2,
          SubText: error,
          tone: "danger",
          allowWrap: true,
          subTextAllowWrap: true,
          children: "Subscription pool unavailable",
        },
        "codex-mux-error",
      ),
    );
  }

  if (!loading) {
    rows.push(
      (0, e7.jsx)(
        _H,
        {
          LeftIcon: CodexMuxPlusIcon,
          onSelect: addSubscription,
          children: busy ? "Adding subscription..." : "Add another subscription",
        },
        "codex-mux-add",
      ),
    );
  }
  rows.push((0, e7.jsx)(CH.Separator, {}, "codex-mux-separator"));
  return (0, e7.jsx)(e7.Fragment, { children: rows });
}

function codexMuxWeeklyWindow(rateLimits) {
  const windows = [rateLimits?.primary, rateLimits?.secondary].filter(Boolean);
  windows.sort(
    (left, right) =>
      (left.windowDurationMins || 0) - (right.windowDurationMins || 0),
  );
  return windows.at(-1) || null;
}

function codexMuxAccountIdentity(account) {
  const parts = String(account.label || "Subscription")
    .split(/\s+-\s+/)
    .map((part) => part.trim())
    .filter(Boolean);
  const name = parts.shift() || "Subscription";
  const metadata = [];
  const addMetadata = (value) => {
    const normalized = String(value || "").trim();
    if (
      !normalized ||
      normalized.toLowerCase() === name.toLowerCase() ||
      metadata.some((item) => item.toLowerCase() === normalized.toLowerCase())
    ) {
      return;
    }
    metadata.push(normalized);
  };
  parts.forEach(addMetadata);
  addMetadata(account.planLabel);
  if (account.preferred) addMetadata("Preferred");
  return { name, metadata };
}

function codexMuxUsageState(remaining) {
  const rounded = remaining == null ? null : Math.max(0, Math.round(remaining));
  if (rounded == null) {
    return {
      level: "unknown",
      textClass: "text-token-description-foreground",
      ariaLabel: "Usage remaining unavailable",
    };
  }
  const ariaLabel = `${rounded}% usage remaining`;
  if (rounded === 0) {
    return { level: "critical", textClass: "text-danger font-medium", ariaLabel };
  }
  if (rounded < 20) {
    return { level: "low", textClass: "text-warning font-medium", ariaLabel };
  }
  if (rounded < 50) {
    return { level: "warning", textClass: "text-warning", ariaLabel };
  }
  return {
    level: "normal",
    textClass: "text-token-description-foreground",
    ariaLabel,
  };
}

function codexMuxResetSummary(resets) {
  if (resets == null) return { count: null, expiresAt: null };
  const count = Math.max(
    0,
    resets.applicable_available_count ?? resets.available_count ?? 0,
  );
  if (count === 0) return { count, expiresAt: null };
  const expiries = (resets.credits || [])
    .filter(
      (credit) =>
        credit.status === "available" && credit.is_supported_by_plan !== false,
    )
    .map((credit) => credit.expires_at)
    .filter((value) => value != null && !Number.isNaN(Date.parse(value)))
    .sort((left, right) => Date.parse(left) - Date.parse(right));
  return { count, expiresAt: expiries[0] || null };
}

function codexMuxResetCopy(count) {
  if (count == null) return "Reset status unavailable";
  if (count === 0) return "No resets available";
  if (count === 1) return "1 reset available";
  return `${count} resets available`;
}

function codexMuxDateTiming(value, now = new Date()) {
  if (value == null) return null;
  const numericValue = typeof value === "number" ? value : null;
  const date = new Date(
    numericValue != null && Number.isFinite(numericValue)
      ? numericValue * 1_000
      : value,
  );
  if (Number.isNaN(date.getTime())) return null;
  const startOfDate = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const startOfNow = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const days = Math.round((startOfDate - startOfNow) / 86_400_000);
  let relativeLabel = null;
  if (days < 0) relativeLabel = "expired";
  else if (days === 0) relativeLabel = "today";
  else if (days === 1) relativeLabel = "tomorrow";
  else if (days <= 7) relativeLabel = `in ${days} days`;
  return {
    dateLabel: new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "numeric",
    }).format(date),
    relativeLabel,
    urgent: days >= 0 && days <= 2,
  };
}

function codexMuxUsageWindows(rateLimits) {
  return [rateLimits?.primary, rateLimits?.secondary]
    .filter(Boolean)
    .map((window) => ({
      usedPercent: window.usedPercent,
      remainingPercent: Math.max(0, 100 - window.usedPercent),
      windowMinutes: window.windowDurationMins || 0,
      resetsAt: window.resetsAt ?? null,
    }));
}

function CodexMuxPlusIcon(props) {
  return (0, e7.jsx)("svg", {
    viewBox: "0 0 20 20",
    fill: "none",
    "aria-hidden": true,
    ...props,
    children: (0, e7.jsx)("path", {
      d: "M10 4.25v11.5M4.25 10h11.5",
      stroke: "currentColor",
      strokeWidth: 1.5,
      strokeLinecap: "round",
    }),
  });
}

function CodexMuxCopyIcon(props) {
  return (0, e7.jsx)("svg", {
    viewBox: "0 0 20 20",
    fill: "none",
    "aria-hidden": true,
    ...props,
    children: (0, e7.jsxs)(e7.Fragment, {
      children: [
        (0, e7.jsx)("rect", {
          x: 6.25,
          y: 6.25,
          width: 9.5,
          height: 9.5,
          rx: 2,
          stroke: "currentColor",
          strokeWidth: 1.5,
        }),
        (0, e7.jsx)("path", {
          d: "M13.75 6.25V6A1.75 1.75 0 0 0 12 4.25H6A1.75 1.75 0 0 0 4.25 6v6c0 .97.78 1.75 1.75 1.75h.25",
          stroke: "currentColor",
          strokeWidth: 1.5,
          strokeLinecap: "round",
        }),
      ],
    }),
  });
}

function CodexMuxResetCreditIcon({ available, className, ...props }) {
  return (0, e7.jsxs)("svg", {
    viewBox: "0 0 20 20",
    fill: "none",
    className: `${className || "icon-sm"} ${available ? "text-chart-green" : "text-warning"}`,
    "aria-hidden": true,
    ...props,
    children: [
      (0, e7.jsx)("rect", {
        x: 1,
        y: 1,
        width: 18,
        height: 18,
        rx: 5,
        fill: "currentColor",
        fillOpacity: 0.16,
      }),
      (0, e7.jsx)("path", {
        d: "M5.25 6.25h9.5v2a1.75 1.75 0 0 0 0 3.5v2h-9.5v-2a1.75 1.75 0 0 0 0-3.5v-2Z",
        stroke: "currentColor",
        strokeWidth: 1.35,
        strokeLinejoin: "round",
      }),
      (0, e7.jsx)("path", {
        d: "M10 7.35v1.1m0 1.1v1.1m0 1.1v.9",
        stroke: "currentColor",
        strokeWidth: 1.2,
        strokeLinecap: "round",
      }),
    ],
  });
}

function CodexMuxMaskedEmail({ email }) {
  return (0, e7.jsxs)(e7.Fragment, {
    children: [
      (0, e7.jsx)("span", {
        className: "group-hover:hidden",
        children: "********",
      }),
      (0, e7.jsx)("span", {
        className: "hidden group-hover:inline",
        children: email,
      }),
    ],
  });
}

function CodexMuxAccountAvatar({ imageUrl, label, className }) {
  const [failed, setFailed] = kXc.useState(false);
  const resolvedImageUrl = jLa(imageUrl || null);
  if (resolvedImageUrl && !failed) {
    return (0, e7.jsx)("img", {
      src: resolvedImageUrl,
      alt: "",
      className: `${className || "icon-sm"} rounded-full object-cover`,
      referrerPolicy: "no-referrer",
      onError: () => setFailed(true),
    });
  }
  const initials = label
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");
  return (0, e7.jsx)("span", {
    className: `${className || "icon-sm"} flex items-center justify-center rounded-full bg-token-charts-purple/10 text-[9px] leading-none text-token-charts-purple`,
    "aria-hidden": true,
    children: initials || "?",
  });
}

function CodexMuxOverlappingAvatars({ accounts, size = "size-20" }) {
  const overlapClass = size === "size-20" ? "-ml-10" : "-ml-2";
  return (0, e7.jsx)("div", {
    className: "flex items-center justify-center",
    children: accounts.map((account, index) =>
      (0, e7.jsx)(
        "span",
        {
          className: `${index === 0 ? "" : overlapClass} rounded-full border-4 border-token-bg-primary`,
          title: account.planLabel
            ? `${account.label} - ${account.planLabel}`
            : account.label,
          children: (0, e7.jsx)(CodexMuxAccountAvatar, {
            imageUrl: account.profileImageUrl,
            label: account.label,
            className: size,
          }),
        },
        account.id,
      ),
    ),
  });
}

function CodexMuxProfileAvatarStack({ onSelect }) {
  const [accounts, setAccounts] = kXc.useState(
    globalThis.__codexMuxCombinedProfileAccounts || [],
  );
  const [selectedId, setSelectedId] = kXc.useState(
    globalThis.__codexMuxSelectedProfileAccountId || null,
  );
  kXc.useEffect(() => {
    let live = true;
    codexMuxRequest("/accounts")
      .then((result) => {
        if (!live) return;
        const connected = (result.accounts || []).filter(
          (account) => account.connected && account.enabled,
        );
        globalThis.__codexMuxCombinedProfileAccounts = connected;
        setAccounts(connected);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, []);
  kXc.useEffect(() => {
    globalThis.__codexMuxSelectedProfileAccountId = null;
    setSelectedId(null);
    onSelect?.();
    return () => {
      globalThis.__codexMuxSelectedProfileAccountId = null;
    };
  }, []);
  if (accounts.length === 0) return null;
  const visibleAccounts = selectedId
    ? accounts.filter((account) => account.id === selectedId)
    : accounts;
  return (0, e7.jsx)("div", {
    className: "mb-4",
    "aria-label": selectedId
      ? "Selected subscription profile"
      : `${accounts.length} connected subscriptions`,
    children: (0, e7.jsx)("div", {
      className: "flex items-center justify-center",
      children: visibleAccounts.map((account, index) =>
        (0, e7.jsx)(
          "button",
          {
            type: "button",
            className: `${index === 0 ? "" : "-ml-5"} rounded-full border-4 border-token-bg-primary transition-transform hover:z-10 hover:scale-105 focus-visible:z-10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-token-focus-border`,
            style: {
              marginLeft: index === 0 ? 0 : -20,
              zIndex: index,
            },
            "aria-label": selectedId
              ? `Show combined profile stats`
              : `Show ${account.label} profile stats`,
            title: account.planLabel
              ? `${account.label} - ${account.planLabel}`
              : account.label,
            onClick: () => {
              const nextId = selectedId === account.id ? null : account.id;
              globalThis.__codexMuxSelectedProfileAccountId = nextId;
              setSelectedId(nextId);
              onSelect?.();
            },
            children: (0, e7.jsx)(CodexMuxAccountAvatar, {
              imageUrl: account.profileImageUrl,
              label: account.label,
              className: "size-20",
            }),
          },
          account.id,
        ),
      ),
    }),
  });
}

function CodexMuxPluginScope() {
  const [accounts, setAccounts] = kXc.useState([]);
  const [selectedId, setSelectedId] = kXc.useState("primary");
  const [loading, setLoading] = kXc.useState(true);
  const queryClient = lt();
  kXc.useEffect(() => {
    let live = true;
    codexMuxRequest("/accounts")
      .then((result) => {
        if (!live) return;
        setAccounts(
          (result.accounts || []).filter(
            (account) => account.connected && account.enabled,
          ),
        );
      })
      .catch(() => {})
      .finally(() => {
        if (live) setLoading(false);
      });
    return () => {
      live = false;
    };
  }, []);

  kXc.useEffect(() => {
    globalThis.__codexMuxPluginAccountId = selectedId;
    return () => {
      delete globalThis.__codexMuxPluginAccountId;
    };
  }, [selectedId]);

  async function selectAccount(accountId) {
    if (accountId === selectedId) return;
    globalThis.__codexMuxPluginAccountId = accountId;
    setSelectedId(accountId);
    await queryClient.invalidateQueries({
      predicate: (query) => {
        const root = query.queryKey?.[0];
        return root === "apps" || root === "plugins" || root === "mcp";
      },
    });
  }

  const selected =
    accounts.find((account) => account.id === selectedId) || accounts[0] || null;

  return (0, e7.jsxs)("div", {
    className:
      "mb-5 rounded-2xl border border-token-border-light p-3",
    children: [
      (0, e7.jsxs)("div", {
        className: "px-1",
        children: [
          (0, e7.jsx)("div", {
            className: "text-sm font-medium text-token-text-primary",
            children: "Plugin connections",
          }),
          (0, e7.jsx)("div", {
            className: "mt-0.5 text-xs text-token-text-secondary",
            children: selected
              ? `Installs are shared. Connection access below is for ${selected.label}.`
              : "Installs are shared. Choose a subscription for connection access.",
          }),
        ],
      }),
      loading
        ? (0, e7.jsx)("div", {
            className: "mt-3 px-1 text-sm text-token-text-tertiary",
            children: "Loading subscriptions...",
          })
        : (0, e7.jsx)("div", {
            className: "mt-3 flex flex-wrap gap-2",
            children: accounts.map((account) => {
              const active = account.id === selected?.id;
              return (0, e7.jsxs)(
                "button",
                {
                  type: "button",
                  className: [
                    "flex items-center gap-2 rounded-xl px-2.5 py-2 text-sm transition-colors",
                    active
                      ? "bg-token-foreground/10 text-token-text-primary"
                      : "text-token-text-secondary hover:bg-token-foreground/5",
                  ].join(" "),
                  "aria-pressed": active,
                  onClick: () => selectAccount(account.id),
                  children: [
                    (0, e7.jsx)(CodexMuxAccountAvatar, {
                      imageUrl: account.profileImageUrl,
                      label: account.label,
                      className: "size-7",
                    }),
                    (0, e7.jsx)("span", {
                      children: account.planLabel
                        ? `${account.label} - ${account.planLabel}`
                        : account.label,
                    }),
                  ],
                },
                account.id,
              );
            }),
          }),
    ],
  });
}

// The thread summary is emitted into a separate lazy-loaded renderer chunk.
// Export the same avatar component so both surfaces share image resolution,
// error handling, and the initials fallback.
globalThis.CodexMuxAccountAvatar = CodexMuxAccountAvatar;
globalThis.codexMuxProfileData = codexMuxProfileData;
globalThis.CodexMuxProfileAvatarStack = (props) =>
  (0, e7.jsx)(CodexMuxProfileAvatarStack, props || {});
globalThis.CodexMuxPluginScope = () =>
  (0, e7.jsx)(CodexMuxPluginScope, {});
