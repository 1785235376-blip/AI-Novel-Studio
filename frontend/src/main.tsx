import React, { lazy, Suspense } from 'react';import ReactDOM from 'react-dom/client';import {QueryClient,QueryClientProvider} from '@tanstack/react-query';import './ui/ui.css';import './ui/fixture.css';import './ui/desktop-craft.css';import {sendHostPing} from './packagedHost';import DesignSystemFixture from './ui/DesignSystemFixture';
import {bootstrapStudioTheme} from './ui/theme';
import {bootstrapLocale, t} from './i18n'; /* [HERMIA-FE-20261025 I18N P0] */
import './i18n/i18n-en.css'; /* [HERMIA-FE-20261025 I18N P0] EN-only header fit */
bootstrapStudioTheme(); /* [HERMIA-FE-20261022] t71u before paint */
bootstrapLocale(); /* sets <html lang> before paint */
const App=lazy(()=>import('./App')),Health=lazy(()=>import('./Health'));
const Page=location.pathname==='/health'?Health:location.pathname==='/ui-fixture'?DesignSystemFixture:App;ReactDOM.createRoot(document.getElementById('root')!).render(<React.StrictMode><QueryClientProvider client={new QueryClient()}><Suspense fallback={<main className="ui-empty" role="status">{t('common.loading')}</main>}><Page/></Suspense></QueryClientProvider></React.StrictMode>);sendHostPing();
