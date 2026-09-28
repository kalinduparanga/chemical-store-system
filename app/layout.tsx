import React from 'react';
import './globals.css';

export const metadata = {
  title: 'Chemical Store Management System',
  description: 'Chemical inventory management – barrels, batches, stock, reports',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
