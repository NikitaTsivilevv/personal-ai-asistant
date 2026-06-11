export const metadata = {
  title: "Personal AI Assistant",
  description: "Live call control (stage 1 stub)",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body style={{ fontFamily: "monospace", margin: "2rem", background: "#0b0e14", color: "#d6dbe5" }}>
        {children}
      </body>
    </html>
  );
}
