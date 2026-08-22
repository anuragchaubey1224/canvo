// The marketing page.
//
// It is written as one argument, in the order someone actually forms it: what is this →
// yes, that problem is mine → wait, you can just describe it? → here is it happening →
// here it is changing something → I could use this → the questions I'd ask → alright.
//
// Every claim on this page is checked against the running product. See content.ts.

import { useEffect, useState } from 'react'
import type { Account } from '../lib/auth'
import { ArrowUpRight, Board, Braces, Check, Database, Logo, Shield, Sparkle } from '../ui/icons'
import { AUDIENCE, CAPABILITIES, FAQS, PROBLEMS, STEPS, USE_CASES } from './content'
import { DiagramDemo } from './DiagramDemo'
import { Nav } from './Nav'
import { BUILD, REFINE } from './scripts'

const YEAR = new Date().getFullYear()

/** One glyph per use case, in the order content.ts lists them. Components rather than
 *  elements — an array of JSX would be an array of children without keys. */
const USE_ICONS = [Board, Shield, Braces, Database]

function Faq() {
  const [open, setOpen] = useState<number | null>(0)
  return (
    <div className="faq">
      {FAQS.map((f, i) => (
        <div key={f.q} className={`faq-item${open === i ? ' is-open' : ''}`}>
          <h3>
            <button
              className="faq-q"
              onClick={() => setOpen(open === i ? null : i)}
              aria-expanded={open === i}
              aria-controls={`faq-${i}`}
            >
              <span>{f.q}</span>
              <span className="faq-mark" aria-hidden="true" />
            </button>
          </h3>
          {/* Kept in the tree and hidden, so in-page search finds an unopened answer. */}
          <div className="faq-a" id={`faq-${i}`} hidden={open !== i}>
            <p>{f.a}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

/** The before/after: the same request as a paragraph, and as the thing it becomes. */
function BeforeAfter() {
  const [after, setAfter] = useState(false)
  return (
    <div className="ba">
      <div className="ba-switch" role="tablist" aria-label="Before and after">
        <button
          role="tab"
          aria-selected={!after}
          className={after ? '' : 'is-on'}
          onClick={() => setAfter(false)}
        >
          What you write
        </button>
        <button
          role="tab"
          aria-selected={after}
          className={after ? 'is-on' : ''}
          onClick={() => setAfter(true)}
        >
          What you get
        </button>
      </div>

      <div className="ba-stage">
        {after ? (
          <DiagramDemo
            script={BUILD}
            caption="The Canvo workspace with the described e-commerce backend drawn as a diagram: a client and API gateway connected to auth, product and order services, with Redis and PostgreSQL beneath them."
          />
        ) : (
          <div className="ba-text">
            <p className="ba-label">Your description</p>
            <p className="ba-quote">{BUILD.prompt}</p>
            <p className="ba-foot">
              One paragraph. Everything below it is derived from this — including the
              assumptions Canvo had to make, which it lists rather than hides.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default function Landing({
  account,
  onNavigate,
}: {
  account: Account | null
  onNavigate: (to: string) => void
}) {
  // The page has its own title; the app sets it back on the way out.
  useEffect(() => {
    const previous = document.title
    document.title = 'Canvo — describe a system, get the diagram'
    return () => {
      document.title = previous
    }
  }, [])

  const go = (to: string) => (e: React.MouseEvent) => {
    e.preventDefault()
    onNavigate(to)
  }

  // One decision, made once: signed in means the CTA opens the product, signed out means
  // it opens the door. Repeated down the page so no CTA is ever the wrong one.
  const startHref = account ? '/dashboard' : '/signup'
  const startLabel = account ? 'Open Canvo' : 'Start creating'

  return (
    <div className="landing">
      <Nav account={account} onNavigate={onNavigate} />

      <main>
        {/* ---- Hero ---- */}
        <section className="hero">
          <div className="wrap">
            <p className="eyebrow">
              <Sparkle size={13} />
              AI system design
            </p>
            <h1 className="hero-title">
              Describe the system.
              <br />
              Canvo draws it.
            </h1>
            <p className="hero-sub">
              Explain an architecture, an auth flow or a schema the way you'd explain it to
              a colleague. Canvo writes the specification, plans the graph, lays it out and
              reviews its own work — and hands you a canvas you can keep editing, by asking
              or by hand.
            </p>
            <div className="hero-cta">
              <a className="btn btn--primary btn--lg" href={startHref} onClick={go(startHref)}>
                {startLabel}
                <ArrowUpRight size={15} />
              </a>
              <a className="btn btn--ghost btn--lg" href="#how">
                See how it works
              </a>
            </div>
            <p className="hero-note">
              Built for engineers and architects. No billing — an email and a password is
              the whole setup.
            </p>
          </div>

          <div className="wrap wrap--wide">
            <DiagramDemo
              script={BUILD}
              caption="The Canvo workspace: a written prompt on the right, a four-stage trace — spec, plan, draw, review — and the resulting architecture diagram on the canvas."
            />
          </div>
        </section>

        {/* ---- Problem ---- */}
        <section className="band">
          <div className="wrap">
            <p className="kicker">The part nobody budgets for</p>
            <h2 className="band-title">
              System design gets messy long before the code does.
            </h2>
            <div className="probs">
              {PROBLEMS.map((p) => (
                <article key={p.n} className="prob">
                  <span className="prob-n">{p.n}</span>
                  <h3>{p.title}</h3>
                  <p>{p.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ---- The shift ---- */}
        <section className="band band--tight">
          <div className="wrap wrap--narrow">
            <p className="kicker">The shift</p>
            <h2 className="band-title">What if you could just describe it?</h2>
            <p className="band-sub">
              Canvo's pipeline is not a model with a drawing tool bolted on. Each stage is a
              separate, inspectable step — which is why the same description produces the
              same diagram twice.
            </p>
            <ol className="flow">
              {[
                ['A description', 'Plain English, a SQL schema, or an OpenAPI document.'],
                ['A written spec', 'Components, flow, phases — and every assumption made.'],
                ['A validated graph', 'Checked and repaired before a shape is drawn.'],
                ['A laid-out diagram', 'Composed and routed, then reviewed for overlaps.'],
                ['A canvas you own', 'Refine by asking, or take over by hand.'],
              ].map(([t, b], i) => (
                <li key={t}>
                  <span className="flow-dot" aria-hidden="true">
                    {i < 4 ? <Check size={12} /> : <Sparkle size={12} />}
                  </span>
                  <span>
                    <strong>{t}</strong>
                    <span>{b}</span>
                  </span>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {/* ---- How it works ---- */}
        <section className="band" id="how">
          <div className="wrap">
            <p className="kicker">How it works</p>
            <h2 className="band-title">Four stages, and you can watch every one.</h2>
            <p className="band-sub">
              The workspace shows the run as it streams. Nothing is marked done before it
              has happened.
            </p>
            <div className="steps">
              {STEPS.map((s) => (
                <article key={s.n} className="step-card">
                  <span className="step-n">{s.n}</span>
                  <h3>{s.title}</h3>
                  <p>{s.body}</p>
                  <p className="step-detail">{s.detail}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ---- Before / after ---- */}
        <section className="band band--tight">
          <div className="wrap wrap--wide">
            <p className="kicker">One paragraph in</p>
            <h2 className="band-title">This is the whole input.</h2>
            <BeforeAfter />
          </div>
        </section>

        {/* ---- Differentiator ---- */}
        <section className="band" id="product">
          <div className="wrap">
            <p className="kicker">Not a drawing tool</p>
            <h2 className="band-title">Your diagram knows what it is.</h2>
            <p className="band-sub">
              Canvo keeps the structure behind the picture — so a change is a change, not a
              redraw.
            </p>
            <div className="caps">
              {CAPABILITIES.map((c) => (
                <article key={c.title} className="cap">
                  <h3>{c.title}</h3>
                  <p>{c.body}</p>
                </article>
              ))}
            </div>
          </div>
        </section>

        {/* ---- Refinement showcase ---- */}
        <section className="band band--tight" id="refine">
          <div className="wrap wrap--wide">
            <p className="kicker">Refining</p>
            <h2 className="band-title">Change it by saying what changed.</h2>
            <p className="band-sub">
              A follow-up is applied as a diff. The two new components arrive; everything
              else stays exactly where it was.
            </p>
            <DiagramDemo
              script={REFINE}
              caption="The same diagram after a follow-up request: a message queue and a fulfilment worker are added and connected to the order service, while the existing components stay in place."
            />
          </div>
        </section>

        {/* ---- Use cases ---- */}
        <section className="band" id="uses">
          <div className="wrap">
            <p className="kicker">Use cases</p>
            <h2 className="band-title">What people draw with it.</h2>
            <div className="uses">
              {USE_CASES.map((u, i) => (
                <article key={u.title} className="use">
                  <span className="use-icon" aria-hidden="true">
                    {(() => {
                      const Icon = USE_ICONS[i]
                      return <Icon size={17} />
                    })()}
                  </span>
                  <h3>{u.title}</h3>
                  <p>{u.body}</p>
                </article>
              ))}
            </div>

            <div className="audience">
              <p className="audience-label">Built for</p>
              <ul>
                {AUDIENCE.map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        {/* ---- FAQ ---- */}
        <section className="band band--tight" id="faq">
          <div className="wrap wrap--narrow">
            <p className="kicker">Questions</p>
            <h2 className="band-title">Before you start.</h2>
            <Faq />
          </div>
        </section>

        {/* ---- Final CTA ---- */}
        <section className="final">
          <div className="wrap wrap--narrow">
            <h2>Your next diagram could start with one sentence.</h2>
            <p>
              Describe what you're building. Canvo turns it into something you can edit,
              share and keep up to date.
            </p>
            <div className="hero-cta">
              <a className="btn btn--primary btn--lg" href={startHref} onClick={go(startHref)}>
                {startLabel}
                <ArrowUpRight size={15} />
              </a>
              {!account && (
                <a className="btn btn--ghost btn--lg" href="/login" onClick={go('/login')}>
                  Log in
                </a>
              )}
            </div>
          </div>
        </section>
      </main>

      <footer className="foot">
        <div className="wrap foot-inner">
          <div className="foot-brand">
            <a className="nav-brand" href="/" onClick={go('/')}>
              <span className="brand-mark" aria-hidden="true">
                <Logo size={17} />
              </span>
              <span className="brand-wordmark">Canvo</span>
            </a>
            <p>Describe a system in plain words and get a diagram you can edit.</p>
          </div>

          <nav className="foot-cols" aria-label="Footer">
            <div>
              <p className="foot-label">Product</p>
              <a href="#how">How it works</a>
              <a href="#product">What makes it different</a>
              <a href="#uses">Use cases</a>
              <a href="#faq">FAQ</a>
            </div>
            <div>
              <p className="foot-label">Account</p>
              {account ? (
                <a href="/dashboard" onClick={go('/dashboard')}>
                  Dashboard
                </a>
              ) : (
                <>
                  <a href="/login" onClick={go('/login')}>
                    Log in
                  </a>
                  <a href="/signup" onClick={go('/signup')}>
                    Sign up
                  </a>
                </>
              )}
            </div>
          </nav>
        </div>
        <div className="wrap foot-base">
          <span>© {YEAR} Canvo</span>
        </div>
      </footer>
    </div>
  )
}
