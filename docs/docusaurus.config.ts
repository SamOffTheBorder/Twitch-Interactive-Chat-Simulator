import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

const config: Config = {
  title: 'Twitch Interactive Chat Simulator',
  tagline: 'AI-powered viewer chat simulation for your Twitch stream',
  favicon: 'img/favicon.ico',

  future: {
    v4: true,
  },

  url: 'https://SamOffTheBorder.github.io',
  baseUrl: '/Twitch-Interactive-Chat-Simulator/',

  organizationName: 'SamOffTheBorder',
  projectName: 'Twitch-Interactive-Chat-Simulator',

  onBrokenLinks: 'throw',

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl: 'https://github.com/SamOffTheBorder/Twitch-Interactive-Chat-Simulator/tree/main/',
        },
        blog: false,
        theme: {
          customCss: './src/css/custom.css',
        },
      } satisfies Preset.Options,
    ],
  ],

  themeConfig: {
    // Replace with your project's social card
    image: 'img/docusaurus-social-card.jpg',
    colorMode: {
      respectPrefersColorScheme: true,
    },
    navbar: {
      title: 'Twitch Chat Simulator',
      items: [
        {
          type: 'docSidebar',
          sidebarId: 'tutorialSidebar',
          position: 'left',
          label: 'Docs',
        },
        {
          href: 'https://github.com/SamOffTheBorder/Twitch-Interactive-Chat-Simulator',
          label: 'GitHub',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'Docs',
          items: [
            { label: 'Getting Started', to: '/docs/intro' },
            { label: 'Configuration', to: '/docs/configuration' },
            { label: 'Bot Accounts', to: '/docs/bot-accounts' },
          ],
        },
        {
          title: 'Project',
          items: [
            {
              label: 'GitHub',
              href: 'https://github.com/SamOffTheBorder/Twitch-Interactive-Chat-Simulator',
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Twitch Interactive Chat Simulator. Built with Docusaurus.`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
