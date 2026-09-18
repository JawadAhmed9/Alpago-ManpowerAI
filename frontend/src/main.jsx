import React from 'react'
import ReactDOM from 'react-dom/client'
import { createBrowserRouter, RouterProvider } from 'react-router-dom'
import './index.css'
import App from './App.jsx'
import Projects from './pages/Projects.jsx'
import ProjectDetail from './pages/ProjectDetail.jsx'
import Employees from './pages/Employees.jsx'
import Calendar from './pages/Calendar.jsx'
import Conflicts from './pages/Conflicts.jsx'
import Masters from './pages/Masters.jsx'

const router = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Projects /> },
      { path: 'projects/:id', element: <ProjectDetail /> },
      { path: 'employees', element: <Employees /> },
      { path: 'masters', element: <Masters /> },
      { path: 'calendar', element: <Calendar /> },
      { path: 'conflicts', element: <Conflicts /> },
    ],
  },
])

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <RouterProvider router={router} />
  </React.StrictMode>,
)
