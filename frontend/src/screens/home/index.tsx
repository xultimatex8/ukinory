import {
  ArrowRight,
  GitCompareArrows,
  Heart,
  UserRound,
  Users,
} from "lucide-react";

import AppHeader from "../../components/LogoHeader";

const features = [
  {
    title: "Discover Individual",
    description: "Find movies based on your personal taste.",
    action: "Start discovering",
    icon: Heart,
  },
  {
    title: "Discover Together",
    description: "Find movies that match the tastes of you and someone else.",
    action: "Discover together",
    icon: Users,
  },
  {
    title: "Compare",
    description: "Compare your movie taste with someone else.",
    action: "Compare tastes",
    icon: GitCompareArrows,
  },
  {
    title: "Profile",
    description: "Manage your profile, preferences and account.",
    action: "View profile",
    icon: UserRound,
  },
];

export default function HomeScreen() {
  return (
    <main className="min-h-screen bg-background text-text">
      <div className="mx-auto min-h-screen w-full max-w-5xl px-6 py-10">
        <section className="pt-16">
          <AppHeader
            title="What do you want to watch?"
            description="Discover movies tailored to your taste or find something to watch together."
          />

          <div className="mt-12 grid gap-4 sm:grid-cols-2">
            {features.map((feature) => {
              const Icon = feature.icon;

              return (
                <button
                  key={feature.title}
                  className="group flex flex-col items-start border border-border bg-surface p-7
                            text-left transition hover:border-primary
                            hover:bg-surface-hover cursor-pointer"
                >
                  <div className="flex w-full items-start justify-between">
                    <div className="flex h-12 w-12 items-center justify-center">
                      <Icon
                        size={38}
                        strokeWidth={1.5}
                        className="text-primary transition group-hover:scale-105"
                      />
                    </div>

                    <ArrowRight
                      size={20}
                      strokeWidth={1.8}
                      className="text-text-muted transition
                                group-hover:translate-x-1
                                group-hover:text-primary"
                    />
                  </div>

                  <h2 className="mt-6 text-xl font-semibold">
                    {feature.title}
                  </h2>

                  <p className="mt-2 text-sm leading-relaxed text-text-muted">
                    {feature.description}
                  </p>

                  <p className="mt-6 text-sm font-medium text-primary">
                    {feature.action}
                  </p>
                </button>
              );
            })}
          </div>
        </section>
      </div>
    </main>
  );
}
