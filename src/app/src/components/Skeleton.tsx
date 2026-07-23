import React from "react";
import s from "./Skeleton.module.css";

export const SkeletonBlock: React.FC<{ width?: string; height?: string; className?: string }> = ({
  width, height, className,
}) => (
  <div
    className={`${s.skeleton} ${s.block} ${className || ""}`}
    style={{ width, height }}
  />
);

export const SkeletonCards: React.FC<{ count?: number }> = ({ count = 4 }) => (
  <div className={s.cardGrid}>
    {Array.from({ length: count }).map((_, i) => (
      <div key={i} className={`${s.skeleton} ${s.card}`} />
    ))}
  </div>
);

export const SkeletonChat: React.FC = () => (
  <div>
    <div className={`${s.skeleton} ${s.chatBubble}`} />
    <div className={`${s.skeleton} ${s.chatBubbleRight}`} />
    <div className={`${s.skeleton} ${s.chatBubble}`} />
    <div className={`${s.skeleton} ${s.chatBubbleRight}`} />
  </div>
);

export const SkeletonText: React.FC<{ lines?: number }> = ({ lines = 3 }) => (
  <div>
    {Array.from({ length: lines }).map((_, i) => (
      <div
        key={i}
        className={`${s.skeleton} ${i === lines - 1 ? s.textShort : s.textMedium}`}
        style={{ marginBottom: 10 }}
      />
    ))}
  </div>
);
