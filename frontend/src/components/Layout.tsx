import React, { useState } from "react";
import {
  makeStyles,
  tokens,
  Button,
  Text,
  Tooltip,
  Popover,
  PopoverTrigger,
  PopoverSurface,
} from "@fluentui/react-components";
import {
  Home24Regular,
  Home24Filled,
  Database24Regular,
  Database24Filled,
  Pipeline24Regular,
  Pipeline24Filled,
  Search24Regular,
  Search24Filled,
  ChartMultiple24Regular,
  ChartMultiple24Filled,
  Chat24Regular,
  Chat24Filled,
  PersonAccounts24Regular,
  ArrowUpload24Regular,
  Settings24Regular,
} from "@fluentui/react-icons";
import { useNavigate, useLocation } from "react-router-dom";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { loginRequest } from "../auth/msalConfig";
import { useUserMode } from "../context/UserModeContext";
import ChatInterface from "./ChatInterface";

const useStyles = makeStyles({
  root: {
    display: "flex",
    flexDirection: "column",
    height: "100vh",
    overflow: "hidden",
  },
  topBar: {
    height: "52px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "0 28px",
    backgroundColor: "#0f172a",
    flexShrink: 0,
    zIndex: 10,
  },
  topBarLeft: {
    display: "flex",
    alignItems: "center",
    gap: "10px",
  },
  topBarRight: {
    display: "flex",
    alignItems: "center",
    gap: "8px",
  },
  breadcrumb: {
    fontSize: "15px",
    fontWeight: 700,
    color: "#ffffff",
    letterSpacing: "-0.2px",
  },
  bodyRow: {
    display: "flex",
    flex: 1,
    overflow: "hidden",
  },
  sidebar: {
    width: "68px",
    backgroundColor: "#ffffff",
    borderRight: "1px solid #f1f5f9",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    paddingTop: "16px",
    flexShrink: 0,
    gap: "8px",
  },
  navItem: {
    width: "48px",
    height: "48px",
    borderRadius: "12px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "3px",
    cursor: "pointer",
    color: "#94a3b8",
    transition: "all 0.15s",
    border: "none",
    backgroundColor: "transparent",
    fontSize: "9px",
    fontWeight: "500",
    letterSpacing: "0.2px",
  },
  navItemActive: {
    width: "48px",
    height: "48px",
    borderRadius: "12px",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    justifyContent: "center",
    gap: "3px",
    cursor: "pointer",
    color: "#2563eb",
    backgroundColor: "#eff6ff",
    border: "none",
    fontSize: "9px",
    fontWeight: "600",
    letterSpacing: "0.2px",
  },
  sidebarBottom: {
    marginTop: "auto",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: "4px",
    paddingBottom: "16px",
  },
  main: {
    flex: 1,
    display: "flex",
    overflow: "hidden",
  },
  content: {
    flex: 1,
    overflowY: "auto",
    backgroundColor: "var(--km-bg, #f9fafb)",
  },
  chatPanel: {
    width: "380px",
    flexShrink: 0,
    borderLeft: `1px solid ${tokens.colorNeutralStroke2}`,
    display: "flex",
    flexDirection: "column",
    backgroundColor: tokens.colorNeutralBackground1,
    overflow: "hidden",
  },
  chatHeader: {
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    padding: "14px 20px",
    borderBottom: `1px solid ${tokens.colorNeutralStroke2}`,
    flexShrink: 0,
  },
  userBadge: {
    width: "32px",
    height: "32px",
    borderRadius: "50%",
    backgroundColor: "#2563eb",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    color: "white",
    fontSize: "11px",
    fontWeight: "600",
    cursor: "pointer",
    border: "none",
  },
});

const Layout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const styles = useStyles();
  const navigate = useNavigate();
  const location = useLocation();
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const { mode, setMode, isAtLeast } = useUserMode();
  const [showChat, setShowChat] = useState(false);

  // AI chat only on pages where AI interaction makes sense
  // Home = upload only, Explore = has built-in chat
  const showChatAvailable = location.pathname === "/insights";

  const handleLogin = () => instance.loginPopup(loginRequest);
  const handleLogout = () => instance.logoutPopup();

  const userName = accounts[0]?.name || "";
  const initials = userName.split(" ").map((n) => n[0]).join("").slice(0, 2).toUpperCase();

  const allNavItems = [
    { path: "/", label: "Home", icon: <Home24Regular />, activeIcon: <Home24Filled /> },
    { path: "/explore", label: "Explore", icon: <Search24Regular />, activeIcon: <Search24Filled /> },
    { path: "/insights", label: "Insights", icon: <ChartMultiple24Regular />, activeIcon: <ChartMultiple24Filled /> },
  ];

  const navItems = allNavItems;

  const currentPage = navItems.find((n) => n.path === location.pathname);
  const pageTitle = location.pathname === "/" ? "" : currentPage?.label || "";

  return (
    <div className={styles.root}>
      {/* Top bar — full width */}
      <div className={styles.topBar}>
        <div className={styles.topBarLeft}>
          <span className={styles.breadcrumb}>Knowledge Mining</span>
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
          {isAuthenticated ? (
            <div className={styles.userBadge} onClick={handleLogout} title={`Sign out (${userName})`}>
              {initials || "U"}
            </div>
          ) : (
            <Tooltip content="Sign In" relationship="label" positioning="after">
              <div className={styles.navItem} onClick={handleLogin}>
                <PersonAccounts24Regular />
              </div>
            </Tooltip>
          )}
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
