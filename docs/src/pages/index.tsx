import type {ReactNode} from 'react';
import Link from '@docusaurus/Link';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import styles from './index.module.css';

export default function Home(): ReactNode {
  const {siteConfig} = useDocusaurusContext();
  return (
    <Layout title={siteConfig.title} description={siteConfig.tagline}>
      <header className={`hero hero--primary ${styles.heroBanner}`}>
        <div className="container">
          <Heading as="h1" className="hero__title">
            {siteConfig.title}
          </Heading>
          <p className="hero__subtitle">{siteConfig.tagline}</p>
          <div className={styles.buttons}>
            <Link className="button button--secondary button--lg" to="/docs">
              Get Started →
            </Link>
          </div>
        </div>
      </header>
      <main>
        <section style={{padding: '3rem 0'}}>
          <div className="container">
            <div className="row">
              <div className="col col--4">
                <div className="text--center padding-horiz--md">
                  <h3>🎙️ Listens to your stream</h3>
                  <p>Captures your live audio via Streamlink and transcribes it in real time using local Whisper — no cloud STT fees.</p>
                </div>
              </div>
              <div className="col col--4">
                <div className="text--center padding-horiz--md">
                  <h3>🤖 AI-generated reactions</h3>
                  <p>Local Ollama (primary) or OpenRouter (fallback) generates short, natural chat messages tailored to each viewer's personality.</p>
                </div>
              </div>
              <div className="col col--4">
                <div className="text--center padding-horiz--md">
                  <h3>👥 Multiple viewer personas</h3>
                  <p>Hype, casual, react, and lurker archetypes — each with their own cooldown, response rate, and messaging style.</p>
                </div>
              </div>
            </div>
          </div>
        </section>
      </main>
    </Layout>
  );
}
