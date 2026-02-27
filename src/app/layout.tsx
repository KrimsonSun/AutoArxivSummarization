import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Auto ArXiv | 每日 CS 论文精选",
  description: "基于 AI 的每日学术论文自动分析与总结平台。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN">
      <body>
        {children}
      </body>
    </html>
  );
}
