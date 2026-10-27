<template>
  <div class="app" :class="{ 'sidebar-collapsed': collapsed, 'sidebar-open': mobileOpen }">
    <aside id="app-sidebar" class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-mark" aria-hidden="true">C</div>
        <div class="brand-text">
          <span class="brand-name">{{ t('nav.companyName') }}</span>
          <span class="brand-subtitle">{{ t('nav.subtitle') }}</span>
        </div>
      </div>

      <nav class="sidebar-nav" :aria-label="t('nav.mainNavigation')">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="nav-link"
          :class="{ active: $route.path === item.to }"
          :title="collapsed ? t(item.label) : null"
        >
          <svg
            class="nav-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path v-for="d in item.icon" :key="d" :d="d" />
          </svg>
          <span class="nav-label">{{ t(item.label) }}</span>
        </router-link>
      </nav>

      <div class="sidebar-footer">
        <ProfileMenu
          :collapsed="collapsed"
          @show-profile-details="showProfileDetails = true"
          @show-tasks="showTasks = true"
        />
        <button
          class="collapse-btn"
          type="button"
          :title="collapsed ? t('nav.expand') : t('nav.collapse')"
          :aria-label="collapsed ? t('nav.expand') : t('nav.collapse')"
          :aria-expanded="!collapsed"
          @click="toggleCollapsed"
        >
          <svg
            class="nav-icon collapse-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="1.75"
            stroke-linecap="round"
            stroke-linejoin="round"
            aria-hidden="true"
          >
            <path d="M15 18l-6-6 6-6" />
          </svg>
          <span class="nav-label">{{ collapsed ? t('nav.expand') : t('nav.collapse') }}</span>
        </button>
      </div>
    </aside>

    <div class="sidebar-backdrop" @click="mobileOpen = false"></div>

    <div class="content-shell">
      <div class="mobile-header">
        <button
          class="menu-btn"
          type="button"
          :aria-label="t('nav.openMenu')"
          aria-controls="app-sidebar"
          :aria-expanded="mobileOpen"
          @click="mobileOpen = true"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.75" stroke-linecap="round" aria-hidden="true">
            <path d="M3 6h18M3 12h18M3 18h18" />
          </svg>
        </button>
        <span class="mobile-title">{{ t('nav.companyName') }}</span>
        <LanguageSwitcher class="mobile-language" />
      </div>

      <div class="topbar">
        <FilterBar />
        <LanguageSwitcher class="desktop-language" />
      </div>

      <main class="main-content">
        <router-view />
      </main>
    </div>

    <ProfileDetailsModal
      :is-open="showProfileDetails"
      @close="showProfileDetails = false"
    />

    <TasksModal
      :is-open="showTasks"
      :tasks="tasks"
      @close="showTasks = false"
      @add-task="addTask"
      @delete-task="deleteTask"
      @toggle-task="toggleTask"
    />
  </div>
</template>

<script>
import { ref, onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api } from './api'
import { useAuth } from './composables/useAuth'
import { useI18n } from './composables/useI18n'
import FilterBar from './components/FilterBar.vue'
import ProfileMenu from './components/ProfileMenu.vue'
import ProfileDetailsModal from './components/ProfileDetailsModal.vue'
import TasksModal from './components/TasksModal.vue'
import LanguageSwitcher from './components/LanguageSwitcher.vue'

const SIDEBAR_STORAGE_KEY = 'app-sidebar-collapsed'

// Feather-style 24x24 stroke icons, one path string per segment
const navItems = [
  { to: '/', label: 'nav.overview', icon: ['M3 3h7v7H3z', 'M14 3h7v7h-7z', 'M14 14h7v7h-7z', 'M3 14h7v7H3z'] },
  { to: '/inventory', label: 'nav.inventory', icon: ['M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z', 'M3.27 6.96L12 12.01l8.73-5.05', 'M12 22.08V12'] },
  { to: '/orders', label: 'nav.orders', icon: ['M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2', 'M9 2h6a1 1 0 0 1 1 1v2a1 1 0 0 1-1 1H9a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1z', 'M9 12h6', 'M9 16h4'] },
  { to: '/spending', label: 'nav.finance', icon: ['M12 1v22', 'M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6'] },
  { to: '/demand', label: 'nav.demandForecast', icon: ['M23 6l-9.5 9.5-5-5L1 18', 'M17 6h6v6'] },
  { to: '/restocking', label: 'nav.restocking', icon: ['M23 4v6h-6', 'M1 20v-6h6', 'M3.51 9a9 9 0 0 1 14.85-3.36L23 10', 'M20.49 15a9 9 0 0 1-14.85 3.36L1 14'] },
  { to: '/reports', label: 'nav.reports', icon: ['M18 20V10', 'M12 20V4', 'M6 20v-6'] }
]

const readCollapsed = () => {
  try {
    return localStorage.getItem(SIDEBAR_STORAGE_KEY) === '1'
  } catch (err) {
    return false
  }
}

export default {
  name: 'App',
  components: {
    FilterBar,
    ProfileMenu,
    ProfileDetailsModal,
    TasksModal,
    LanguageSwitcher
  },
  setup() {
    const { currentUser } = useAuth()
    const { t } = useI18n()
    const route = useRoute()
    const showProfileDetails = ref(false)
    const showTasks = ref(false)
    const collapsed = ref(readCollapsed())
    const mobileOpen = ref(false)
    const apiTasks = ref([])

    // Merge mock tasks from currentUser with API tasks
    const tasks = computed(() => {
      return [...currentUser.value.tasks, ...apiTasks.value]
    })

    const loadTasks = async () => {
      try {
        apiTasks.value = await api.getTasks()
      } catch (err) {
        console.error('Failed to load tasks:', err)
      }
    }

    const addTask = async (taskData) => {
      try {
        const newTask = await api.createTask(taskData)
        // Add new task to the beginning of the array
        apiTasks.value.unshift(newTask)
      } catch (err) {
        console.error('Failed to add task:', err)
      }
    }

    const deleteTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const isMockTask = currentUser.value.tasks.some(t => t.id === taskId)

        if (isMockTask) {
          // Remove from mock tasks
          const index = currentUser.value.tasks.findIndex(t => t.id === taskId)
          if (index !== -1) {
            currentUser.value.tasks.splice(index, 1)
          }
        } else {
          // Remove from API tasks
          await api.deleteTask(taskId)
          apiTasks.value = apiTasks.value.filter(t => t.id !== taskId)
        }
      } catch (err) {
        console.error('Failed to delete task:', err)
      }
    }

    const toggleTask = async (taskId) => {
      try {
        // Check if it's a mock task (from currentUser)
        const mockTask = currentUser.value.tasks.find(t => t.id === taskId)

        if (mockTask) {
          // Toggle mock task status
          mockTask.status = mockTask.status === 'pending' ? 'completed' : 'pending'
        } else {
          // Toggle API task
          const updatedTask = await api.toggleTask(taskId)
          const index = apiTasks.value.findIndex(t => t.id === taskId)
          if (index !== -1) {
            apiTasks.value[index] = updatedTask
          }
        }
      } catch (err) {
        console.error('Failed to toggle task:', err)
      }
    }

    const toggleCollapsed = () => {
      collapsed.value = !collapsed.value
      try {
        localStorage.setItem(SIDEBAR_STORAGE_KEY, collapsed.value ? '1' : '0')
      } catch (err) {
        // Storage can be unavailable (private mode); the toggle still works this session
      }
    }

    // The drawer is an overlay, so close it after navigating or on Escape
    watch(() => route.path, () => {
      mobileOpen.value = false
    })

    const handleKeydown = (event) => {
      if (event.key === 'Escape') mobileOpen.value = false
    }

    onMounted(() => {
      loadTasks()
      window.addEventListener('keydown', handleKeydown)
    })

    onUnmounted(() => {
      window.removeEventListener('keydown', handleKeydown)
    })

    return {
      t,
      navItems,
      collapsed,
      mobileOpen,
      toggleCollapsed,
      showProfileDetails,
      showTasks,
      tasks,
      addTask,
      deleteTask,
      toggleTask
    }
  }
}
</script>

<style>
:root {
  --sidebar-width: 248px;
  --sidebar-bg: #0f172a;
  --sidebar-border: rgba(255, 255, 255, 0.07);
  --sidebar-text: #94a3b8;
  --sidebar-hover: rgba(255, 255, 255, 0.06);
  --sidebar-active: rgba(59, 130, 246, 0.18);
  --accent: #3b82f6;
  --surface-border: #e6eaf0;
  --shadow-card: 0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.05);
  --shadow-card-hover: 0 8px 20px rgba(15, 23, 42, 0.08);
}

* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

body {
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
  background: #f5f7fb;
  color: #1e293b;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.app {
  min-height: 100vh;
}

/* ---------- Sidebar ---------- */

.sidebar {
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  width: var(--sidebar-width);
  display: flex;
  flex-direction: column;
  background: var(--sidebar-bg);
  z-index: 200;
  transition: width 0.2s ease, transform 0.2s ease;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  min-height: 72px;
  padding: 1.25rem 1.25rem 1rem;
}

.brand-mark {
  flex: none;
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6, #2563eb);
  color: #ffffff;
  font-size: 1.0625rem;
  font-weight: 700;
  box-shadow: 0 2px 8px rgba(37, 99, 235, 0.45);
}

.brand-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
  line-height: 1.25;
}

.brand-name {
  color: #f8fafc;
  font-size: 0.9375rem;
  font-weight: 650;
  letter-spacing: -0.01em;
}

.brand-subtitle {
  color: #64748b;
  font-size: 0.75rem;
}

.sidebar-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0.5rem 0.75rem;
  overflow-y: auto;
}

.nav-link {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.625rem 0.75rem;
  border-radius: 8px;
  color: var(--sidebar-text);
  font-size: 0.9rem;
  font-weight: 500;
  text-decoration: none;
  transition: background 0.15s ease, color 0.15s ease;
}

.nav-link:hover {
  background: var(--sidebar-hover);
  color: #e2e8f0;
}

.nav-link.active {
  background: var(--sidebar-active);
  color: #ffffff;
}

.nav-link.active .nav-icon {
  color: #60a5fa;
}

.nav-link.active::before {
  content: '';
  position: absolute;
  top: 8px;
  bottom: 8px;
  left: -0.75rem;
  width: 3px;
  border-radius: 0 3px 3px 0;
  background: var(--accent);
}

.nav-link:focus-visible,
.collapse-btn:focus-visible,
.menu-btn:focus-visible {
  outline: 2px solid #60a5fa;
  outline-offset: 2px;
}

.nav-icon {
  flex: none;
  width: 20px;
  height: 20px;
}

.nav-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-footer {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  padding: 0.75rem;
  border-top: 1px solid var(--sidebar-border);
}

.collapse-btn {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  border: none;
  border-radius: 8px;
  background: transparent;
  color: var(--sidebar-text);
  font-family: inherit;
  font-size: 0.85rem;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.15s ease, color 0.15s ease;
}

.collapse-btn:hover {
  background: var(--sidebar-hover);
  color: #e2e8f0;
}

.collapse-icon {
  transition: transform 0.2s ease;
}

.sidebar-collapsed .collapse-icon {
  transform: rotate(180deg);
}

/* ---------- Content shell ---------- */

.content-shell {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 100vh;
  margin-left: var(--sidebar-width);
  transition: margin-left 0.2s ease;
}

.topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 2rem;
  background: rgba(255, 255, 255, 0.9);
  border-bottom: 1px solid var(--surface-border);
  backdrop-filter: blur(8px);
}

.mobile-header,
.sidebar-backdrop {
  display: none;
}

.main-content {
  flex: 1;
  width: 100%;
  max-width: 1480px;
  margin: 0 auto;
  padding: 1.75rem 2rem 3rem;
}

/* Desktop: collapse to an icon rail */
@media (min-width: 901px) {
  .app.sidebar-collapsed {
    --sidebar-width: 72px;
  }

  .sidebar-collapsed .brand-text,
  .sidebar-collapsed .nav-label {
    display: none;
  }

  .sidebar-collapsed .sidebar-brand {
    justify-content: center;
    padding-right: 0;
    padding-left: 0;
  }

  .sidebar-collapsed .nav-link,
  .sidebar-collapsed .collapse-btn {
    justify-content: center;
    padding-right: 0;
    padding-left: 0;
  }
}

/* Mobile: the sidebar becomes an off-canvas drawer */
@media (max-width: 900px) {
  .sidebar {
    width: 280px;
    visibility: hidden;
    transform: translateX(-100%);
    transition: transform 0.2s ease, visibility 0s linear 0.2s;
  }

  .sidebar-open .sidebar {
    visibility: visible;
    transform: none;
    box-shadow: 0 0 40px rgba(0, 0, 0, 0.35);
    transition-delay: 0s;
  }

  .content-shell {
    margin-left: 0;
  }

  .sidebar-backdrop {
    display: block;
    position: fixed;
    inset: 0;
    z-index: 190;
    background: rgba(15, 23, 42, 0.5);
    opacity: 0;
    pointer-events: none;
    transition: opacity 0.2s ease;
  }

  .sidebar-open .sidebar-backdrop {
    opacity: 1;
    pointer-events: auto;
  }

  .mobile-header {
    position: sticky;
    top: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    padding: 0.75rem 1rem;
    background: #ffffff;
    border-bottom: 1px solid var(--surface-border);
  }

  .menu-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    border: 1px solid var(--surface-border);
    border-radius: 8px;
    background: #ffffff;
    color: #334155;
    cursor: pointer;
  }

  .menu-btn svg {
    width: 20px;
    height: 20px;
  }

  .mobile-title {
    font-size: 1rem;
    font-weight: 650;
    color: #0f172a;
    letter-spacing: -0.01em;
  }

  .topbar {
    position: static;
    padding: 0.75rem 1rem;
  }

  /* The header carries the language switcher on small screens */
  .desktop-language {
    display: none;
  }

  .mobile-language {
    margin-left: auto;
  }

  .main-content {
    padding: 1.25rem 1rem 2rem;
  }

  .collapse-btn {
    display: none;
  }
}

/* ---------- Shared page styles (inherited by every view) ---------- */

.page-header {
  margin-bottom: 1.5rem;
}

.page-header h2 {
  font-size: 1.625rem;
  font-weight: 700;
  color: #0f172a;
  margin-bottom: 0.25rem;
  letter-spacing: -0.025em;
}

.page-header p {
  color: #64748b;
  font-size: 0.9375rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat-card {
  background: #ffffff;
  padding: 1.25rem 1.5rem;
  border-radius: 12px;
  border: 1px solid var(--surface-border);
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease;
}

.stat-card:hover {
  border-color: #d5dbe5;
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-1px);
}

.stat-label {
  color: #64748b;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: 0.5rem;
}

.stat-value {
  font-size: 2rem;
  font-weight: 700;
  color: #0f172a;
  letter-spacing: -0.025em;
  line-height: 1.15;
}

.stat-card.warning .stat-value {
  color: #ea580c;
}

.stat-card.success .stat-value {
  color: #059669;
}

.stat-card.danger .stat-value {
  color: #dc2626;
}

.stat-card.info .stat-value {
  color: #2563eb;
}

.card {
  background: #ffffff;
  border-radius: 12px;
  padding: 1.5rem;
  border: 1px solid var(--surface-border);
  box-shadow: var(--shadow-card);
  margin-bottom: 1.5rem;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 1px solid #eef1f6;
}

.card-title {
  font-size: 1rem;
  font-weight: 650;
  color: #0f172a;
  letter-spacing: -0.015em;
}

.table-container {
  overflow-x: auto;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: #f8fafc;
  border-bottom: 1px solid var(--surface-border);
}

th {
  text-align: left;
  padding: 0.625rem 1rem;
  font-weight: 600;
  color: #64748b;
  font-size: 0.6875rem;
  text-transform: uppercase;
  letter-spacing: 0.06em;
}

td {
  padding: 0.75rem 1rem;
  border-top: 1px solid #f1f5f9;
  color: #334155;
  font-size: 0.875rem;
}

tbody tr:first-child td {
  border-top: 0;
}

tbody tr {
  transition: background-color 0.15s ease;
}

tbody tr:hover {
  background: #f8fafc;
}

.badge {
  display: inline-block;
  padding: 0.2rem 0.625rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  white-space: nowrap;
}

.badge.success {
  background: #d1fae5;
  color: #065f46;
}

.badge.warning {
  background: #fed7aa;
  color: #92400e;
}

.badge.danger {
  background: #fecaca;
  color: #991b1b;
}

.badge.info {
  background: #dbeafe;
  color: #1e40af;
}

.badge.increasing {
  background: #d1fae5;
  color: #065f46;
}

.badge.decreasing {
  background: #fecaca;
  color: #991b1b;
}

.badge.stable {
  background: #e0e7ff;
  color: #3730a3;
}

.badge.high {
  background: #fecaca;
  color: #991b1b;
}

.badge.medium {
  background: #fed7aa;
  color: #92400e;
}

.badge.low {
  background: #dbeafe;
  color: #1e40af;
}

.loading {
  text-align: center;
  padding: 3rem;
  color: #64748b;
  font-size: 0.938rem;
}

.error {
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #991b1b;
  padding: 1rem;
  border-radius: 8px;
  margin: 1rem 0;
  font-size: 0.938rem;
}
</style>
