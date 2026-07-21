// layout.js
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import MotionProvider from "./MotionProvider";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata = {
  title: "AtypicalTick",
  description: "Un sistema para ayudarte a dar el siguiente paso, no solo a organizar tareas.",
};

export const viewport = {
  colorScheme: "dark",
};

// src/app/layout.js
export default function RootLayout({ children }) {
  return (
    <html lang="es" className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <MotionProvider>{children}</MotionProvider>
      </body>
    </html>
  );
}