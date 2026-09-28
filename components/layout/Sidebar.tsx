import React from 'react';

export default function Sidebar() {
  return (
    <aside style={{ width: '200px', backgroundColor: '#2d3748', color: '#fff', minHeight: '100vh', padding: '1rem' }}>
      <nav>
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          <li><a href="/" style={{ color: '#fff', textDecoration: 'none' }}>Dashboard</a></li>
          {/* Add more navigation items as needed */}
        </ul>
      </nav>
    </aside>
  );
}
