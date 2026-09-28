import React from 'react';
import Header from '@/components/layout/Header';
import Sidebar from '@/components/layout/Sidebar';

export default function HomePage() {
  return (
    <>
      <Header />
      <div style={{ display: 'flex' }}>
        <Sidebar />
        <main style={{ flexGrow: 1, padding: '1rem' }}>
          <h2>Chemical Store Management System Dashboard</h2>
          <p>This is a placeholder page. The full UI will be built here.</p>
        </main>
      </div>
    </>
  );
}
