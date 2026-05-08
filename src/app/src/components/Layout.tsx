import React, { useState, useEffect } from "react";
import {
  Button,
  Text,
  Tooltip,
} from "@fluentui/react-components";
import {
  Home24Regular,
  Home24Filled,
  Database24Regular,
  Database24Filled,
  Search24Regular,
  Search24Filled,
  ChartMultiple24Regular,
  ChartMultiple24Filled,
  Chat24Regular,
  Chat24Filled,
  PersonAccounts24Regular,
} from "@fluentui/react-icons";
import { useNavigate, useLocation } from "react-router-dom";
import ChatInterface from "./ChatInterface";
import { useAppState } from "../context/AppStateContext";
import uiConfig from "../config/ui-config.json";
import styles from "./Layout.module.css";

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const [showChat, setShowChat] = useState(false);
  const [userName, setUserName] = useState("");
  const { dashboardHeadline } = useAppState();

  useEffect(() => {
    // Fetch user info from EasyAuth
    fetch(`${window.location.origin}/.auth/me`)
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        const claims = data?.[0]?.user_claims || [];
        const name = claims.find((c: any) => c.typ === "name")?.val || "";
        setUserName(name);
      })
      .catch(() => {});
  }, []);

  const isAuthenticated = !!userName;
  const showChatAvailable = location.pathname === "/insights";

  const handleLogin = () => { window.location.href = "/.auth/login/aad"; };
  const handleLogout = () => { window.location.href = "/.auth/logout"; };

  const initials = userName.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();

  const allNavItems = [
    { path: "/", label: "Home", icon: <Home24Regular />, activeIcon: <Home24Filled /> },
    { path: "/insights", label: "Insights", icon: <ChartMultiple24Regular />, activeIcon: <ChartMultiple24Filled /> },
    { path: "/explore", label: "Explore", icon: <Search24Regular />, activeIcon: <Search24Filled /> },
    // { path: "/data-sources", label: "Sources", icon: <Database24Regular />, activeIcon: <Database24Filled /> },
  ];

  const navItems = allNavItems;

  const currentPage = navItems.find((n) => n.path === location.pathname);
  const pageTitle = location.pathname === "/" ? "" : currentPage?.label || "";

  return (
    <div className={styles.root}>
      {/* Top bar — full width */}
      <div className={styles.topBar}>
        <div className={styles.topBarLeft}>
          <span className={styles.breadcrumb}>
            {process.env.REACT_APP_BRANDING_NAME || "Knowledge Mining"}
            {uiConfig.useCaseName && (
              <span style={{ fontWeight: 400, color: "#94a3b8" }}>
                {" | "}{uiConfig.useCaseName}
              </span>
            )}
          </span>
        </div>
        <div className={styles.topBarRight}>
          {showChatAvailable && (
            <Button
              appearance="subtle"
              size="small"
              icon={showChat ? <Chat24Filled /> : <Chat24Regular />}
              onClick={() => setShowChat(!showChat)}
              style={{ color: "#cbd5e1" }}
            >
              <span style={{ color: "#cbd5e1" }}>{showChat ? "Hide Chat" : "Ask your data"}</span>
            </Button>
          )}
          {isAuthenticated ? (
            <Tooltip content={`Sign out (${userName})`} relationship="label" positioning="below">
              <div className={styles.userBadge} onClick={handleLogout}>
                {initials || "U"}
              </div>
            </Tooltip>
          ) : (
            <Button
              appearance="subtle"
              size="small"
              icon={<PersonAccounts24Regular />}
              onClick={handleLogin}
              style={{ color: "#cbd5e1" }}
            >
              <span style={{ color: "#cbd5e1" }}>Sign in</span>
            </Button>
          )}
        </div>
      </div>

      {/* Body: sidebar + content */}
      <div className={styles.bodyRow}>
        {/* Sidebar */}
        <nav className={styles.sidebar}>
          {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
              <div
                key={item.path}
                className={isActive ? styles.navItemActive : styles.navItem}
                onClick={() => navigate(item.path)}
              >
                {isActive ? item.activeIcon : item.icon}
                <span>{item.label}</span>
              </div>
          );
        })}
        <div className={styles.sidebarBottom}>
        </div>
      </nav>

      {/* Main content */}
      <div className={styles.main}>
          <div className={styles.content}>{children}</div>
          {showChat && showChatAvailable && (
            <div className={styles.chatPanel}>
              <div className={styles.chatHeader}>
                <Text weight="semibold" size={400}>Ask your data</Text>
                <Button appearance="subtle" size="small" onClick={() => setShowChat(false)}>
                  Close
                </Button>
              </div>
              <ChatInterface />
            </div>
          )}
      </div>
      </div>
    </div>
  );
};

export default Layout;
