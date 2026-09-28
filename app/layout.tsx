import React from 'react';
import './globals.css';
import Header from '@/components/layout/Header';
import Sidebar from '@/components/layout/Sidebar';

export const metadata = {
  title: 'Chemical Store Management System',
  description: 'Manage chemicals, stock, reports, and more',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Header />
        <div style={{ display: 'flex' }}>
          <Sidebar />
          <main style={{ flexGrow: 1, padding: '1rem' }}>{children}</main>
        </div>
      </body>
    </html>
  );
}
