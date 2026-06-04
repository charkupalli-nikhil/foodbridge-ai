import { Link } from "react-router-dom";
import "../App.css";

function Home() {
  const features = [
    {
      icon: "🍱",
      title: "Post Surplus Food",
      description:
        "Restaurants, canteens and event organisers can quickly list available food for donation.",
    },
    {
      icon: "📍",
      title: "Nearby Matching",
      description:
        "The platform helps connect donations with nearby NGOs and collection partners.",
    },
    {
      icon: "⚡",
      title: "Urgency Priority",
      description:
        "Food listings are prioritised using preparation time, category and pickup deadline.",
    },
    {
      icon: "📊",
      title: "Impact Dashboard",
      description:
        "Track completed pickups, food servings redistributed and donation trends.",
    },
  ];

  const steps = [
    {
      number: "01",
      title: "Donor Lists Food",
      text: "Add food type, quantity, pickup address and collection deadline.",
    },
    {
      number: "02",
      title: "System Prioritises",
      text: "FoodBridge assigns urgency and suggests suitable nearby NGOs.",
    },
    {
      number: "03",
      title: "NGO Accepts Pickup",
      text: "The NGO accepts the request and collects the available food.",
    },
    {
      number: "04",
      title: "Impact Recorded",
      text: "Completed donations are counted in the analytics dashboard.",
    },
  ];

  return (
    <div className="app">
      <header className="navbar">
        <Link to="/" className="brand">
          <div className="brand-icon">🍃</div>
          <div>
            <h2>FoodBridge AI</h2>
            <p>Rescue food. Serve communities.</p>
          </div>
        </Link>

        <nav className="nav-links">
          <a href="#features">Features</a>
          <a href="#workflow">How it Works</a>
          <a href="#impact">Impact</a>
        </nav>

        <div className="nav-actions">
          <Link to="/login" className="login-btn">
            Login
          </Link>

          <Link to="/register" className="signup-btn">
            Register
          </Link>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="hero-content">
            <p className="tagline">SMART FOOD RECOVERY PLATFORM</p>

            <h1>
              Connect surplus food with
              <span> people who need it.</span>
            </h1>

            <p className="hero-description">
              FoodBridge AI connects restaurants, college canteens and event
              organisers with NGOs for faster food collection, intelligent
              prioritisation and transparent impact tracking.
            </p>

            <div className="hero-buttons">
              <Link to="/register" className="primary-btn">
                Donate Food
              </Link>

              <Link to="/login" className="secondary-btn">
                Find Donations
              </Link>
            </div>

            <div className="hero-stats" id="impact">
              <div>
                <h3>0+</h3>
                <p>Donations</p>
              </div>

              <div>
                <h3>0+</h3>
                <p>Meals Saved</p>
              </div>

              <div>
                <h3>0+</h3>
                <p>NGO Partners</p>
              </div>
            </div>
          </div>

          <div className="hero-visual">
            <div className="visual-card">
              <div className="live-badge">● New Donation Available</div>

              <div className="food-card">
                <div className="food-info">
                  <div className="food-icon">🍛</div>

                  <div>
                    <h3>Cooked Meals</h3>
                    <p>College Canteen</p>
                  </div>
                </div>

                <span className="high-priority">HIGH</span>
              </div>

              <div className="details">
                <div>
                  <span>Quantity</span>
                  <strong>80 servings</strong>
                </div>

                <div>
                  <span>Distance</span>
                  <strong>2.4 km</strong>
                </div>

                <div>
                  <span>Pickup Before</span>
                  <strong>45 min</strong>
                </div>
              </div>

              <Link to="/login" className="accept-btn">
                Accept Pickup Request
              </Link>
            </div>
          </div>
        </section>

        <section className="features-section" id="features">
          <div className="section-heading">
            <p>CORE FEATURES</p>
            <h2>Technology that makes donation faster</h2>
          </div>

          <div className="features-grid">
            {features.map((feature) => (
              <article className="feature-card" key={feature.title}>
                <div className="feature-icon">{feature.icon}</div>
                <h3>{feature.title}</h3>
                <p>{feature.description}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="workflow-section" id="workflow">
          <div className="section-heading">
            <p>SIMPLE WORKFLOW</p>
            <h2>How FoodBridge AI works</h2>
          </div>

          <div className="workflow-grid">
            {steps.map((step) => (
              <article className="workflow-card" key={step.number}>
                <span>{step.number}</span>
                <h3>{step.title}</h3>
                <p>{step.text}</p>
              </article>
            ))}
          </div>
        </section>
      </main>

      <footer className="footer">
        <h3>FoodBridge AI</h3>
        <p>An intelligent surplus food recovery and distribution platform.</p>
      </footer>
    </div>
  );
}

export default Home;