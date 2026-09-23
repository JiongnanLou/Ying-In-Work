/**
 * 石头剪刀布 —— 核心对战逻辑模块（零依赖，可移植）。
 *
 * 把「石头剪刀布 · 三局两胜」的对战规则、电脑策略模型、对局状态机
 * 全部封装在这里，与任何 UI / 框架解耦。移植时只需引入本文件：
 *
 *   浏览器 <script> 直引：  window.ShiTouJianDao
 *   CommonJS：              require('./game.js')
 *   AMD / ES Module：       见结尾导出
 *
 * 使用示例见 example.html 与 README.md。
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else if (typeof define === "function" && define.amd) {
    define(factory);
  } else {
    root.ShiTouJianDao = factory();
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  // ---- 手势常量 ----
  var HAND = {
    ROCK: "rock",
    SCISSORS: "scissors",
    PAPER: "paper",
  };

  // 克制关系：key 打败 value
  var BEATS = {
    rock: "scissors",
    scissors: "paper",
    paper: "rock",
  };

  // 展示用（中文名 / emoji），可按需替换语种
  var NAME = {
    rock: "石头",
    scissors: "剪刀",
    paper: "布",
  };
  var EMOJI = {
    rock: "✊",
    scissors: "✌️",
    paper: "✋",
  };

  /**
   * 判定本回合胜负。
   * @param {string} user 用户出拳（HAND 之一）
   * @param {string} cpu  电脑出拳（HAND 之一）
   * @returns {"win"|"lose"|"draw"}
   */
  function judge(user, cpu) {
    if (user === cpu) return "draw";
    return BEATS[user] === cpu ? "win" : "lose";
  }

  /**
   * 随机出拳。
   * @returns {string} HAND 之一
   */
  function randomHand() {
    var keys = Object.keys(HAND);
    return HAND[keys[Math.floor(Math.random() * keys.length)]];
  }

  /**
   * 电脑策略模型：频率学习 + 反制。
   *
   * 它观察用户历史出拳，若某种手势出现比例不低于 threshold，
   * 就倾向出「能克制该手势」的手势；否则随机。相比纯随机更有“模型感”。
   *
   * @param {number} [threshold=0.55] 触发反制的频率阈值（0~1）
   * @param {number} [minSample=4]    最少历史样本数，低于它时纯随机
   */
  function Strategy(threshold, minSample) {
    this.threshold = threshold == null ? 0.55 : threshold;
    this.minSample = minSample == null ? 4 : minSample;
    this.history = [];
  }

  /** 记录用户本次出拳，供模型学习。 */
  Strategy.prototype.record = function (userHand) {
    this.history.push(userHand);
  };

  /** 根据历史决定电脑本次出拳。 */
  Strategy.prototype.choose = function () {
    var self = this;
    var total = self.history.length;
    if (total >= self.minSample) {
      var counts = { rock: 0, scissors: 0, paper: 0 };
      self.history.forEach(function (h) {
        counts[h]++;
      });
      for (var hand in BEATS) {
        if (counts[hand] / total >= self.threshold) {
          // 用户偏爱 hand，电脑出「能打败 hand」的手势
          for (var candidate in BEATS) {
            if (BEATS[candidate] === hand) return candidate;
          }
        }
      }
    }
    return randomHand();
  };

  /** 清空历史。 */
  Strategy.prototype.reset = function () {
    this.history.length = 0;
  };

  /**
   * 「三局两胜」对局状态机。
   *
   * @param {number} [winsNeeded=2]  先赢几局算胜（三局两胜 = 2）
   * @param {Strategy} [strategy]    可选的策略模型，默认新建一个
   */
  function Session(winsNeeded, strategy) {
    this.winsNeeded = winsNeeded == null ? 2 : winsNeeded;
    this.strategy = strategy || new Strategy();
    this.userWins = 0;
    this.cpuWins = 0;
    this.finished = false;
    this.winner = null; // null | "user" | "cpu"
  }

  /**
   * 打一局。
   * @param {string} userHand 用户出拳
   * @returns {{user: string, cpu: string, outcome: string,
   *            userWins: number, cpuWins: number,
   *            finished: boolean, winner: string|null}}
   *           outcome 为 "win"|"lose"|"draw"；平局时不计胜负、本局作废。
   */
  Session.prototype.play = function (userHand) {
    var cpuHand = this.strategy.choose();
    this.strategy.record(userHand);
    var outcome = judge(userHand, cpuHand);

    if (outcome === "win") {
      this.userWins++;
    } else if (outcome === "lose") {
      this.cpuWins++;
    }

    if (this.userWins >= this.winsNeeded) {
      this.finished = true;
      this.winner = "user";
    } else if (this.cpuWins >= this.winsNeeded) {
      this.finished = true;
      this.winner = "cpu";
    }

    return {
      user: userHand,
      cpu: cpuHand,
      outcome: outcome,
      userWins: this.userWins,
      cpuWins: this.cpuWins,
      finished: this.finished,
      winner: this.winner,
    };
  };

  /** 复位对局。 */
  Session.prototype.reset = function () {
    this.userWins = 0;
    this.cpuWins = 0;
    this.finished = false;
    this.winner = null;
    this.strategy.reset();
  };

  // ---- 导出 ----
  return {
    HAND: HAND,
    BEATS: BEATS,
    NAME: NAME,
    EMOJI: EMOJI,
    judge: judge,
    randomHand: randomHand,
    Strategy: Strategy,
    Session: Session,
  };
});