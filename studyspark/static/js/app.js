/* StudySpark front-end interactions — vanilla JS, no frameworks.
   Every block is commented so you can learn from it. */

document.addEventListener("DOMContentLoaded", () => {

  /* ---------------------------------------------------------
     0) 🌙 Dark mode toggle (theme choice is saved in localStorage)
     --------------------------------------------------------- */
  const themeBtn = document.getElementById("theme-toggle");
  const syncThemeIcon = () => {
    const dark = document.documentElement.getAttribute("data-theme") === "dark";
    if (themeBtn) themeBtn.textContent = dark ? "☀️" : "🌙";
  };
  if (themeBtn) {
    themeBtn.addEventListener("click", () => {
      const dark = document.documentElement.getAttribute("data-theme") === "dark";
      if (dark) {
        document.documentElement.removeAttribute("data-theme");
        localStorage.setItem("theme", "light");
      } else {
        document.documentElement.setAttribute("data-theme", "dark");
        localStorage.setItem("theme", "dark");
      }
      syncThemeIcon();
    });
    syncThemeIcon();
  }

  /* ---------------------------------------------------------
     0b) 🔊 Text-to-speech — the browser can READ, for free!
         (Web Speech API, works offline-ish, zero backend code)
     --------------------------------------------------------- */
  const speak = (text) => {
    if (!("speechSynthesis" in window)) return;
    speechSynthesis.cancel();  // stop any card still talking
    const u = new SpeechSynthesisUtterance(text);
    u.rate = 0.95;
    speechSynthesis.speak(u);
  };

  // Tiny speaker buttons on flashcards (don't flip the card when clicking it!)
  document.querySelectorAll(".tts-btn").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      speak(btn.dataset.say || "");
    });
  });

  /* ---------------------------------------------------------
     0c) 🎉 Confetti — pure JS celebration, no libraries
     --------------------------------------------------------- */
  const EMOJIS = ["🎉", "✨", "⭐", "💜", "⚡", "🏆"];
  const fireConfetti = (count = 40) => {
    for (let i = 0; i < count; i++) {
      const bit = document.createElement("span");
      bit.className = "confetti-piece";
      bit.textContent = EMOJIS[Math.floor(Math.random() * EMOJIS.length)];
      bit.style.left = Math.random() * 100 + "vw";
      bit.style.fontSize = 0.8 + Math.random() * 1.2 + "rem";
      bit.style.animationDuration = 1.8 + Math.random() * 1.8 + "s";
      bit.style.animationDelay = Math.random() * 0.4 + "s";
      document.body.appendChild(bit);
      setTimeout(() => bit.remove(), 4500);
    }
  };

  /* ---------------------------------------------------------
     1) Flashcards: click (or press Enter/Space) to flip a card.
     --------------------------------------------------------- */
  const cards = document.querySelectorAll(".flashcard:not(.study-card)");
  const flipCount = document.getElementById("flip-count");
  let flipped = 0;

  cards.forEach((card) => {
    const flip = () => {
      if (!card.dataset.flippedOnce) {
        card.dataset.flippedOnce = "1";
        flipped++;
        if (flipCount) flipCount.textContent = `${flipped}/${cards.length} cards studied`;
      }
      card.classList.toggle("flipped");
    };
    card.addEventListener("click", flip);
    card.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        flip();
      }
    });
  });

  /* ---------------------------------------------------------
     2) Quiz: click an option -> feedback -> score -> XP to server.
     --------------------------------------------------------- */
  const quizRoot = document.querySelector(".quiz");
  const questions = document.querySelectorAll(".quiz-question");
  let correctCount = 0;
  let answeredCount = 0;

  questions.forEach((q) => {
    const answerIndex = Number(q.dataset.answer);
    const options = q.querySelectorAll(".quiz-option");
    const explanation = q.querySelector(".quiz-explanation");

    options.forEach((opt) => {
      opt.addEventListener("click", () => {
        if (q.dataset.answered) return;
        q.dataset.answered = "1";
        answeredCount++;

        if (Number(opt.dataset.index) === answerIndex) correctCount++;

        options.forEach((o) => {
          const i = Number(o.dataset.index);
          if (i === answerIndex) o.classList.add("correct");
          else if (o === opt) o.classList.add("wrong");
          o.disabled = true;
        });

        if (explanation) explanation.hidden = false;

        if (answeredCount === questions.length) {
          const scoreCard = document.getElementById("quiz-score");
          const scoreText = document.getElementById("quiz-score-text");
          if (scoreCard && scoreText) {
            const pct = Math.round((correctCount / questions.length) * 100);
            let msg = `You scored ${correctCount}/${questions.length} (${pct}%). `;
            if (pct === 100) { msg += "Perfect! 🏆"; fireConfetti(60); }
            else if (pct >= 70) { msg += "Great job! 🌟"; fireConfetti(25); }
            else if (pct >= 40) msg += "Keep practicing! 💪";
            else msg += "Review your flashcards and try again! 📚";
            scoreText.textContent = msg;
            scoreCard.hidden = false;
            scoreCard.scrollIntoView({ behavior: "smooth" });

            if (quizRoot && quizRoot.dataset.authed === "1") {
              fetch("/api/quiz-score", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  set_id: Number(quizRoot.dataset.setId),
                  correct: correctCount,
                  total: questions.length,
                }),
              })
                .then((r) => r.json())
                .then((d) => {
                  const xpText = document.getElementById("quiz-xp-text");
                  if (xpText && !d.error) {
                    xpText.textContent =
                      `+${d.xp_earned} XP earned · total ${d.total_xp} XP` +
                      (d.new_best ? ` · 🏆 NEW best score: ${d.best_score}%` : ` · best score: ${d.best_score}%`) +
                      (d.streak > 1 ? ` · 🔥 ${d.streak} day streak` : "");
                  }
                })
                .catch(() => {});
            }
          }
        }
      });
    });
  });

  /* ---------------------------------------------------------
     3) Live character counter on the create page textarea.
     --------------------------------------------------------- */
  const notes = document.getElementById("notes");
  const counter = document.getElementById("char-count");
  if (notes && counter) {
    const update = () => {
      counter.textContent = notes.value.length.toLocaleString();
    };
    notes.addEventListener("input", update);
    update();
  }

  /* ---------------------------------------------------------
     4) File upload: show the chosen file name in the drop zone.
     --------------------------------------------------------- */
  const fileInput = document.getElementById("notes_file");
  const dropText = document.getElementById("file-drop-text");
  if (fileInput && dropText) {
    fileInput.addEventListener("change", () => {
      const drop = fileInput.closest(".file-drop");
      if (fileInput.files.length) {
        const f = fileInput.files[0];
        dropText.innerHTML = `<strong>${f.name}</strong> — ${(f.size / 1024).toFixed(0)} KB · looks good!`;
        if (drop) drop.classList.add("has-file");
      } else {
        if (drop) drop.classList.remove("has-file");
      }
    });
  }

  /* ---------------------------------------------------------
     5) 🔗 Copy share link button
     --------------------------------------------------------- */
  const copyBtn = document.getElementById("copy-share");
  const shareInput = document.getElementById("share-link");
  if (copyBtn && shareInput) {
    copyBtn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(shareInput.value);
        copyBtn.textContent = "Copied! ✅";
      } catch (_) {
        shareInput.select();
        document.execCommand("copy");
        copyBtn.textContent = "Copied! ✅";
      }
      setTimeout(() => (copyBtn.textContent = "Copy"), 2000);
    });
  }

  /* ---------------------------------------------------------
     5b) 🔎 Library search — instant filter while you type
     --------------------------------------------------------- */
  const libSearch = document.getElementById("lib-search");
  if (libSearch) {
    const setCards = document.querySelectorAll(".set-card");
    libSearch.addEventListener("input", () => {
      const q = libSearch.value.trim().toLowerCase();
      let visible = 0;
      setCards.forEach((card) => {
        const title = (card.querySelector("h3")?.textContent || "").toLowerCase();
        const show = !q || title.includes(q);
        card.style.display = show ? "" : "none";
        if (show) visible++;
      });
      libSearch.setAttribute(
        "aria-label",
        visible === setCards.length ? "Search your sets" : `${visible} of ${setCards.length} sets match`
      );
    });
  }

  /* ---------------------------------------------------------
     6) 🎯 STUDY MODE + 🔁 SPACED REPETITION
        We remember EVERY card result and send them to the
        server, which schedules the next review per card.
     --------------------------------------------------------- */
  const studyWrap = document.querySelector(".study-wrap");
  if (studyWrap) {
    const rawData = document.getElementById("cards-data");
    let deck = rawData ? JSON.parse(rawData.textContent) : [];
    let idx = 0;
    let results = [];  // [{front, state}] — the spaced-repetition memory

    const card = document.getElementById("study-card");
    const front = document.getElementById("study-front");
    const back = document.getElementById("study-back");
    const pos = document.getElementById("study-pos");
    const fill = document.getElementById("study-fill");
    const zone = document.querySelector(".study-card-zone");
    const finishBox = document.getElementById("study-finish");
    const resultsText = document.getElementById("study-results");
    const xpBox = document.getElementById("study-xp");

    const shuffle = (arr) => {
      for (let i = arr.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [arr[i], arr[j]] = [arr[j], arr[i]];
      }
      return arr;
    };

    const showCard = () => {
      card.classList.remove("flipped");
      front.textContent = deck[idx].front;
      back.textContent = deck[idx].back;
      pos.textContent = idx + 1;
      fill.style.width = `${(idx / deck.length) * 100}%`;
    };

    const finish = () => {
      fill.style.width = "100%";
      zone.hidden = true;
      finishBox.hidden = false;
      const known = results.filter((r) => r.state === "known").length;
      resultsText.textContent = `✔ Knew ${known} · ✖ Still learning ${results.length - known} — of ${results.length} cards`;
      fireConfetti(30);

      fetch(`/set/${studyWrap.dataset.setId}/finish-study`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ results }),
      })
        .then((r) => r.json())
        .then((d) => {
          let text = `+${d.xp_earned} XP · total ${d.total_xp} XP · 🔥 ${d.streak} day streak`;
          if (d.due_remaining === 0) text += " · 🔁 all caught up!";
          else text += ` · 🔁 ${d.due_remaining} still due`;
          xpBox.textContent = text;
        })
        .catch(() => {});
    };

    const advance = (knewIt) => {
      results.push({ front: deck[idx].front, state: knewIt ? "known" : "learning" });
      if (idx + 1 < deck.length) {
        idx++;
        showCard();
      } else {
        finish();
      }
    };

    card.addEventListener("click", () => card.classList.toggle("flipped"));

    document.getElementById("btn-know").addEventListener("click", () => advance(true));
    document.getElementById("btn-again").addEventListener("click", () => advance(false));
    document.getElementById("study-shuffle").addEventListener("click", () => {
      deck = shuffle(deck);
      idx = 0; results = [];
      finishBox.hidden = true; zone.hidden = false;
      showCard();
    });
    document.getElementById("study-restart").addEventListener("click", () => {
      idx = 0; results = [];
      finishBox.hidden = true; zone.hidden = false;
      showCard();
    });

    // 🔊 speak whichever side is currently visible
    const studyTts = document.getElementById("study-tts");
    if (studyTts) {
      studyTts.addEventListener("click", () => {
        speak(card.classList.contains("flipped") ? deck[idx].back : deck[idx].front);
      });
    }

    document.addEventListener("keydown", (e) => {
      if (finishBox && !finishBox.hidden) return;
      if (e.key === " ") {
        e.preventDefault();
        card.classList.toggle("flipped");
      } else if (e.key === "ArrowRight") {
        advance(true);
      } else if (e.key === "ArrowLeft") {
        advance(false);
      }
    });

    showCard();
  }

  /* ---------------------------------------------------------
     7) Auto-dismiss success messages after 5 seconds.
     --------------------------------------------------------- */
  setTimeout(() => {
    document.querySelectorAll(".flash-success").forEach((el) => {
      el.style.transition = "opacity 0.5s ease";
      el.style.opacity = "0";
      setTimeout(() => el.remove(), 500);
    });
  }, 5000);
});
