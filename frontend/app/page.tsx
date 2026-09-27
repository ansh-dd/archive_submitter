"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";

type Stats = {
  domains: number;
  urls: number;
  new_urls: number;
  changed_urls: number;
  queued: number;
  successful: number;
  failed: number;
  success_rate: number;
  avg_archive_ms: number;
  avg_crawl_ms: number;
};

type Health = {
  api: string;
  database: string;
  redis: string;
  task_mode: string;
  archive_provider: string;
  crawler_concurrency: number;
  max_response_size_mb: number;
};

type LatestScan = {
  new_urls_found: number;
  changed_urls_found: number;
  urls_found: number;
  pages_fetched: number;
  duration_ms: number;
  status: string;
};

type Domain = {
  id: number;
  base_url: string;
  hostname: string;
  status: string;
  last_scan_at: string | null;

  total_urls: number;
  new_urls: number;
  changed_urls: number;
  archived_urls: number;
  pending_jobs: number;
  failed_jobs: number;

  scheduled_scan_enabled: boolean;
  next_scan_at: string | null;

  latest_scan?: LatestScan | null;
};

export default function Dashboard() {
  const pathname = usePathname();

  const [stats, setStats] = useState<Stats>({
    domains: 0,
    urls: 0,
    new_urls: 0,
    changed_urls: 0,
    queued: 0,
    successful: 0,
    failed: 0,
    success_rate: 0,
    avg_archive_ms: 0,
    avg_crawl_ms: 0,
  });

  const [health, setHealth] = useState<Health | null>(null);

  const [domains, setDomains] = useState<Domain[]>([]);

  const [url, setUrl] = useState("");

  const [message, setMessage] = useState("");

  const [error, setError] = useState("");

  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const timestamp = Date.now();

      const [s, d, h] = await Promise.all([
        api<Stats>(`/api/stats?_=${timestamp}`),

        api<Domain[]>(
          `/api/domains?_=${timestamp}`
        ),

        api<Health>(
          `/api/system/health?_=${timestamp}`
        ),
      ]);

      setStats(s);

      /*
       * The backend normally returns an array.
       * Keep this defensive check so an unexpected response
       * cannot silently clear the dashboard.
       */
      if (Array.isArray(d)) {
        setDomains(d);
      } else {
        console.error(
          "Unexpected /api/domains response:",
          d
        );
      }

      setHealth(h);

      setError("");
    } catch (e: any) {
      console.error(
        "Dashboard refresh failed:",
        e
      );

      setError(
        e?.message ||
          "Could not refresh dashboard."
      );
    }
  }, []);

  useEffect(() => {
    /*
     * Always refresh whenever the dashboard route becomes active.
     */
    if (pathname === "/") {
      refresh();
    }

    /*
     * Normal auto refresh.
     */
    const timer = window.setInterval(() => {
      if (
        document.visibilityState ===
        "visible"
      ) {
        refresh();
      }
    }, 3000);

    /*
     * Important when returning using the browser Back button.
     */
    const handlePageShow = () => {
      refresh();
    };

    /*
     * Important when the browser window becomes active again.
     */
    const handleFocus = () => {
      refresh();
    };

    /*
     * Important when returning from another tab/page.
     */
    const handleVisibilityChange = () => {
      if (
        document.visibilityState ===
        "visible"
      ) {
        refresh();
      }
    };

    /*
     * Browser history navigation.
     */
    const handlePopState = () => {
      refresh();
    };

    window.addEventListener(
      "pageshow",
      handlePageShow
    );

    window.addEventListener(
      "focus",
      handleFocus
    );

    window.addEventListener(
      "popstate",
      handlePopState
    );

    document.addEventListener(
      "visibilitychange",
      handleVisibilityChange
    );

    return () => {
      window.clearInterval(timer);

      window.removeEventListener(
        "pageshow",
        handlePageShow
      );

      window.removeEventListener(
        "focus",
        handleFocus
      );

      window.removeEventListener(
        "popstate",
        handlePopState
      );

      document.removeEventListener(
        "visibilitychange",
        handleVisibilityChange
      );
    };
  }, [pathname, refresh]);

  async function addDomain(
    e: FormEvent
  ) {
    e.preventDefault();

    setBusy(true);
    setError("");
    setMessage("");

    try {
      const d = await api<Domain>(
        "/api/domains",
        {
          method: "POST",
          body: JSON.stringify({
            url,
          }),
        }
      );

      setUrl("");

      setMessage(
        `Added ${d.hostname}. Start discovery when ready.`
      );

      await refresh();
    } catch (e: any) {
      setError(
        e?.message ||
          "Unable to add domain."
      );
    } finally {
      setBusy(false);
    }
  }

  async function action(
    id: number,
    action: "scan" | "archive"
  ) {
    setError("");
    setMessage("");

    try {
      const body =
        action === "archive"
          ? JSON.stringify({
              force: false,
              changed_only: true,
            })
          : undefined;

      const r: any = await api(
        `/api/domains/${id}/${action}`,
        {
          method: "POST",
          body,
        }
      );

      let msg =
        r.message ||
        `${action} started successfully.`;

      if (r.created !== undefined) {
        msg +=
          ` Created ${r.created};` +
          ` skipped ${r.skipped};` +
          ` blocked ${r.blocked_or_inaccessible}.`;
      }

      setMessage(msg);

      await refresh();
    } catch (e: any) {
      setError(
        e?.message ||
          `Unable to ${action} domain.`
      );
    }
  }

  return (
    <>
      {/* HERO */}

      <section className="hero">
        <div>
          <h1>
            Archive Operations Dashboard
          </h1>

          <p>
            Fault-tolerant discovery,
            change detection, queued
            archiving, and historical
            proof.
          </p>
        </div>
      </section>

      {/* SYSTEM HEALTH */}

      <section className="panel">
        <div className="sectionHead">
          <div>
            <h2>System health</h2>

            <p className="small">
              Runtime architecture and
              safety limits.
            </p>
          </div>
        </div>

        <div className="healthRow">
          <span>
            API{" "}
            <b className="ok">
              {health?.api ?? "…"}
            </b>
          </span>

          <span>
            Database{" "}
            <b
              className={
                health?.database ===
                "healthy"
                  ? "ok"
                  : "bad"
              }
            >
              {health?.database ?? "…"}
            </b>
          </span>

          <span>
            Redis{" "}
            <b>
              {health?.redis ?? "…"}
            </b>
          </span>

          <span>
            Mode{" "}
            <b>
              {health?.task_mode ?? "…"}
            </b>
          </span>

          <span>
            Archive provider{" "}
            <b>
              {health?.archive_provider ??
                "…"}
            </b>
          </span>

          <span>
            Crawler concurrency{" "}
            <b>
              {health?.crawler_concurrency ??
                "…"}
            </b>
          </span>
        </div>
      </section>

      {/* ADD WEBSITE */}

      <section
        className="panel"
        style={{
          marginTop: 18,
        }}
      >
        <div className="sectionHead">
          <div>
            <h2>Add website</h2>

            <p className="small">
              Only public HTTP/HTTPS
              domains are accepted.
              Private/internal destinations
              are blocked.
            </p>
          </div>
        </div>

        <form
          className="formRow"
          onSubmit={addDomain}
        >
          <input
            placeholder="https://example.com"
            value={url}
            onChange={(e) =>
              setUrl(e.target.value)
            }
            required
          />

          <button
            className="primary"
            disabled={busy}
            type="submit"
          >
            {busy
              ? "Adding…"
              : "Add Domain"}
          </button>
        </form>

        {message && (
          <div className="notice">
            {message}
          </div>
        )}

        {error && (
          <div className="notice error">
            {error}
          </div>
        )}
      </section>

      {/* STATISTICS */}

      <section className="grid">
        <div className="stat">
          <span>Domains</span>
          <b>{stats.domains}</b>
        </div>

        <div className="stat">
          <span>
            URLs discovered
          </span>

          <b>{stats.urls}</b>
        </div>

        <div className="stat">
          <span>
            Changed pages
          </span>

          <b>
            {stats.changed_urls}
          </b>
        </div>

        <div className="stat">
          <span>
            Queue active
          </span>

          <b>{stats.queued}</b>
        </div>

        <div className="stat">
          <span>
            Archive success
          </span>

          <b>
            {stats.success_rate}%
          </b>
        </div>
      </section>

      {/* PERFORMANCE */}

      <section
        className="panel"
        style={{
          marginBottom: 18,
        }}
      >
        <div className="sectionHead">
          <h2>Performance</h2>

          <span className="muted small">
            Measured from completed
            runs/submissions
          </span>
        </div>

        <div className="healthRow">
          <span>
            Successful submissions{" "}
            <b>
              {stats.successful}
            </b>
          </span>

          <span>
            Failed jobs{" "}
            <b>{stats.failed}</b>
          </span>

          <span>
            Avg crawl{" "}
            <b>
              {stats.avg_crawl_ms} ms
            </b>
          </span>

          <span>
            Avg archive request{" "}
            <b>
              {stats.avg_archive_ms} ms
            </b>
          </span>
        </div>
      </section>

      {/* DOMAINS */}

      <section className="panel">
        <div className="sectionHead">
          <h2>Domains</h2>

          <span className="muted small">
            {domains.length} stored •
            auto-refresh every 3 seconds
          </span>
        </div>

        {domains.length === 0 ? (
          <div className="empty">
            No domains yet. Add one
            above.
          </div>
        ) : (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Domain</th>
                  <th>Status</th>
                  <th>URLs</th>
                  <th>Changed</th>
                  <th>Archived</th>
                  <th>Pending</th>
                  <th>Last scan</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {domains.map((d) => (
                  <tr key={d.id}>
                    <td>
                      {/*
                       * Normal anchor navigation is intentional.
                       * This prevents stale Next.js router-state
                       * restoration when the user presses Back.
                       */}
                      <a
                        className="link"
                        href={`/domains/${d.id}`}
                      >
                        {d.hostname}
                      </a>

                      <div className="muted small mono">
                        {d.base_url}
                      </div>
                    </td>

                    <td>
                      <span
                        className={`badge ${d.status}`}
                      >
                        {d.status}
                      </span>
                    </td>

                    <td>
                      {d.total_urls}
                    </td>

                    <td>
                      {d.changed_urls}
                    </td>

                    <td>
                      {d.archived_urls}
                    </td>

                    <td>
                      {d.pending_jobs}
                    </td>

                    <td>
                      {d.last_scan_at
                        ? new Date(
                            d.last_scan_at
                          ).toLocaleString()
                        : "Never"}

                      {d.latest_scan && (
                        <div className="small muted">
                          {
                            d.latest_scan
                              .new_urls_found
                          }{" "}
                          new •{" "}
                          {
                            d.latest_scan
                              .changed_urls_found
                          }{" "}
                          changed •{" "}
                          {
                            d.latest_scan
                              .pages_fetched
                          }{" "}
                          fetched
                        </div>
                      )}
                    </td>

                    <td>
                      <div className="actions">
                        <button
                          disabled={
                            d.status ===
                            "SCANNING"
                          }
                          onClick={() =>
                            action(
                              d.id,
                              "scan"
                            )
                          }
                        >
                          Scan
                        </button>

                        <button
                          className="primary"
                          disabled={
                            !d.total_urls
                          }
                          onClick={() =>
                            action(
                              d.id,
                              "archive"
                            )
                          }
                        >
                          Archive
                          new/changed
                        </button>

                        <a
                          className="button"
                          href={`/domains/${d.id}`}
                        >
                          Details
                        </a>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}