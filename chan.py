import tkinter as tk
from heapq import heappush, heappop
import random, time
from collections import deque

# ===== 설정 =====
ROWS, COLS = 25, 41   # 홀수 권장(통로폭 1)
SIZE = 24
MARGIN = 2
W, H = COLS * SIZE, ROWS * SIZE

EMPTY, WALL, START, GOAL, OPEN, CLOSED, PATH, PLAYER, HINT = range(9)
COLORS = {
    EMPTY:  "#1e1e1e",
    WALL:   "#444",
    START:  "#2ecc71",
    GOAL:   "#e74c3c",
    OPEN:   "#2980b9",
    CLOSED: "#8e44ad",
    PATH:   "#f1c40f",
    PLAYER: "#00d1ff",
    HINT:   "#f9e79f",
}

def idx(r, c): return r * COLS + c
def in_bounds(r,c): return 0<=r<ROWS and 0<=c<COLS

def manhattan(a, b): (r1,c1),(r2,c2)=a,b; return abs(r1-r2)+abs(c1-c2)

class Grid:
    def __init__(self):
        self.grid = [EMPTY]*(ROWS*COLS)
        self.start = None
        self.goal = None
        self.player = None
    def clear(self):
        self.grid = [EMPTY]*(ROWS*COLS); self.start=None; self.goal=None; self.player=None
    def get(self, r,c): return self.grid[idx(r,c)]
    def set(self, r,c,v): self.grid[idx(r,c)] = v
    def walkable(self, r,c): return in_bounds(r,c) and self.get(r,c) != WALL
    def neighbors4(self, r,c):
        for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
            nr,nc=r+dr,c+dc
            if in_bounds(nr,nc) and self.get(nr,nc)!=WALL:
                yield nr,nc

class App:
    def __init__(self, root):
        self.root = root
        root.title("Maze Game (steps=0, time=0.0s)")
        self.cv = tk.Canvas(root, width=W, height=H, bg="#000"); self.cv.pack()
        self.grid = Grid()
        self.mode_right_click = 0
        self.animating = False
        self.steps_per_tick = 40  # [ ] 로 조절
        self.move_count = 0
        self.start_time = None
        self.timer_after = None
        self.hint_cell = None

        # 이벤트
        self.cv.bind("<Button-1>", self.on_left)
        self.cv.bind("<B1-Motion>", self.on_left_drag)
        self.cv.bind("<Button-3>", self.on_right)
        for key in ["<Left>","<Right>","<Up>","<Down>"]:
            root.bind(key, self.on_arrow)
        for key in ["a","d","w","s","A","D","W","S"]:
            root.bind(key, self.on_wasd)
        root.bind("<space>", self.run_astar)
        root.bind("c", self.clear)
        root.bind("m", self.start_maze_animation)
        root.bind("[", self.slower)
        root.bind("]", self.faster)
        root.bind("h", self.hint)

        self.draw_all()

    # ---------- 그리기 ----------
    def draw_cell(self, r,c):
        x0=c*SIZE+MARGIN; y0=r*SIZE+MARGIN
        x1=x0+SIZE-MARGIN*2; y1=y0+SIZE-MARGIN*2
        self.cv.create_rectangle(x0,y0,x1,y1, fill=COLORS[self.grid.get(r,c)], outline="#222")
    def draw_all(self):
        self.cv.delete("all")
        for r in range(ROWS):
            for c in range(COLS):
                self.draw_cell(r,c)

    # ---------- 공통 유틸 ----------
    def set_status(self):
        elapsed = 0.0 if self.start_time is None else (time.time()-self.start_time)
        self.root.title(f"Maze Game (steps={self.move_count}, time={elapsed:.1f}s)")

    def start_timer(self):
        if self.start_time is None:
            self.start_time = time.time()
            self._tick_timer()

    def _tick_timer(self):
        if self.start_time is None: return
        self.set_status()
        self.timer_after = self.root.after(200, self._tick_timer)

    def stop_timer(self):
        if self.timer_after:
            self.root.after_cancel(self.timer_after)
            self.timer_after = None

    # ---------- 입력(편집/시작·목표 수동 지정) ----------
    def on_left(self, e):
        if self.animating: return
        r,c = e.y//SIZE, e.x//SIZE
        if not in_bounds(r,c): return
        if (self.grid.start==(r,c)) or (self.grid.goal==(r,c)) or (self.grid.player==(r,c)): return
        self.grid.set(r,c, WALL if self.grid.get(r,c)==EMPTY else EMPTY)
        self.draw_cell(r,c)
    def on_left_drag(self, e): self.on_left(e)

    def on_right(self, e):
        if self.animating: return
        r,c = e.y//SIZE, e.x//SIZE
        if not in_bounds(r,c): return
        if self.mode_right_click == 0:
            if self.grid.get(r,c)==WALL: return
            # reset old start/player
            if self.grid.start:
                sr,sc=self.grid.start
                if self.grid.get(sr,sc)==START: self.grid.set(sr,sc,EMPTY); self.draw_cell(sr,sc)
            if self.grid.player:
                pr,pc=self.grid.player
                if self.grid.get(pr,pc)==PLAYER: self.grid.set(pr,pc,EMPTY); self.draw_cell(pr,pc)
            self.grid.start=(r,c); self.grid.set(r,c,START)
            self.grid.player=(r,c); self.grid.set(r,c,PLAYER)
            self.mode_right_click=1
            self.move_count=0; self.start_time=None; self.set_status()
        else:
            if self.grid.get(r,c)==WALL: return
            if self.grid.goal:
                gr,gc=self.grid.goal
                if self.grid.get(gr,gc)==GOAL: self.grid.set(gr,gc,EMPTY); self.draw_cell(gr,gc)
            self.grid.goal=(r,c); self.grid.set(r,c,GOAL)
            self.mode_right_click=0
        self.draw_cell(r,c)

    # ---------- 플레이어 이동 ----------
    def on_arrow(self, e):
        key = e.keysym
        d = {"Left":(0,-1),"Right":(0,1),"Up":(-1,0),"Down":(1,0)}[key]
        self.try_move(*d)
    def on_wasd(self, e):
        k = e.keysym.lower()
        d = {"a":(0,-1),"d":(0,1),"w":(-1,0),"s":(1,0)}[k]
        self.try_move(*d)

    def try_move(self, dr, dc):
        if self.animating or not self.grid.player: return
        r,c = self.grid.player
        nr,nc = r+dr, c+dc
        if not in_bounds(nr,nc): return
        if self.grid.get(nr,nc)==WALL: return

        # 기존 플레이어 칸 복구(시작이면 START, 아니면 EMPTY/경로 유지)
        prev_state = START if (r,c)==self.grid.start else (PATH if self.grid.get(r,c)==PATH else EMPTY)
        self.grid.set(r,c, prev_state); self.draw_cell(r,c)

        # 새 위치
        self.grid.player = (nr,nc)
        # 목표면 우선 목표 색 유지 + player 테두리 느낌으로 덮어쓰기
        if (nr,nc)==self.grid.goal:
            self.grid.set(nr,nc,GOAL); self.draw_cell(nr,nc)
        self.grid.set(nr,nc,PLAYER); self.draw_cell(nr,nc)

        # 첫 이동이면 타이머 시작
        self.move_count += 1
        self.start_timer()
        self.set_status()

        # 도착 체크
        if (nr,nc)==self.grid.goal:
            self.stop_timer()
            self.root.title(self.root.title() + "  🎉 GOAL!")

    # ---------- 힌트(한 칸) ----------
    def hint(self, _=None):
        if self.animating or not (self.grid.player and self.grid.goal): return
        step = self._next_step_astar(self.grid.player, self.grid.goal)
        # 이전 힌트 지우기
        if self.hint_cell and self.grid.get(*self.hint_cell)==HINT:
            self.grid.set(*self.hint_cell, EMPTY); self.draw_cell(*self.hint_cell)
        if step:
            r,c = step
            if (r,c)!=self.grid.goal and (r,c)!=self.grid.player:
                self.grid.set(r,c,HINT); self.draw_cell(r,c)
                self.hint_cell = (r,c)
        else:
            self.hint_cell = None

    def _next_step_astar(self, start, goal):
        """start->goal 최단경로에서 다음 한 칸 반환(없으면 None)."""
        g={start:0}; f={start:manhattan(start,goal)}; came={}
        pq=[]; heappush(pq,(f[start],start))
        closed=set()
        while pq:
            _,cur=heappop(pq)
            if cur in closed: continue
            closed.add(cur)
            if cur==goal:
                path=[]
                while cur in came:
                    path.append(cur); cur=came[cur]
                path.reverse()
                return path[0] if path else None
            for nb in self.grid.neighbors4(*cur):
                if nb in closed: continue
                tg=g[cur]+1
                if tg<g.get(nb,float("inf")):
                    came[nb]=cur; g[nb]=tg; f[nb]=tg+manhattan(nb,goal)
                    heappush(pq,(f[nb],nb))
        return None

    # ---------- 자동해답(A*) ----------
    def run_astar(self, _=None):
        if not (self.grid.start and self.grid.goal) or self.animating: return
        # 기존 PATH/OPEN/CLOSED/HINT 지우기(벽/시작/목표/플레이어 유지)
        for r in range(ROWS):
            for c in range(COLS):
                if self.grid.get(r,c) in (OPEN,CLOSED,PATH,HINT):
                    self.grid.set(r,c,EMPTY)
        self.draw_all()
        # 다시 표식
        if self.grid.start:  self.grid.set(*self.grid.start, START); self.draw_cell(*self.grid.start)
        if self.grid.goal:   self.grid.set(*self.grid.goal, GOAL);   self.draw_cell(*self.grid.goal)
        if self.grid.player: self.grid.set(*self.grid.player, PLAYER); self.draw_cell(*self.grid.player)

        start,goal=self.grid.start,self.grid.goal
        g={start:0}; f={start:manhattan(start,goal)}; came={}
        pq=[]; heappush(pq,(f[start],start))
        open_set={start}; closed=set(); steps=0

        while pq:
            _,cur=heappop(pq)
            if cur in closed: continue
            open_set.discard(cur); closed.add(cur)
            if cur==goal:
                path=[]
                while cur in came:
                    path.append(cur); cur=came[cur]
                path.reverse()
                for (r,c) in path:
                    if (r,c) not in (self.grid.start,self.grid.goal,self.grid.player):
                        self.grid.set(r,c,PATH); self.draw_cell(r,c)
                return
            for nb in self.grid.neighbors4(*cur):
                if nb in closed: continue
                tg=g[cur]+1
                if tg<g.get(nb,float("inf")):
                    came[nb]=cur; g[nb]=tg
                    f[nb]=tg+manhattan(nb,goal)
                    heappush(pq,(f[nb],nb)); open_set.add(nb)
            steps+=1
            if steps%8==0:
                for r,c in closed:
                    if (r,c) not in (self.grid.start,self.grid.goal,self.grid.player) and self.grid.get(r,c)==EMPTY:
                        self.grid.set(r,c,CLOSED); self.draw_cell(r,c)
                for _,(r,c) in pq[:min(len(pq),80)]:
                    if (r,c) not in (self.grid.start,self.grid.goal,self.grid.player) and self.grid.get(r,c) in (EMPTY,CLOSED):
                        self.grid.set(r,c,OPEN); self.draw_cell(r,c)

    # ---------- 미로 애니메이션 ----------
    def start_maze_animation(self, _=None):
        if self.animating: return
        self.animating=True
        self.move_count=0; self.start_time=None; self.set_status()
        # 모두 벽
        for r in range(ROWS):
            for c in range(COLS):
                self.grid.set(r,c,WALL)
        self.grid.start=self.grid.goal=self.grid.player=None
        self.draw_all()

        # DFS 백트래킹 준비(홀수 격자)
        self._stack=[]
        sr=random.randrange(1,ROWS,2); sc=random.randrange(1,COLS,2)
        self._stack.append((sr,sc))
        self.grid.set(sr,sc,EMPTY); self.draw_cell(sr,sc)
        self.root.after(0, self._maze_tick)

    def _maze_tick(self):
        steps = self.steps_per_tick
        while steps>0 and self._stack:
            r,c = self._stack[-1]
            dirs=[(2,0),(-2,0),(0,2),(0,-2)]
            random.shuffle(dirs)
            carved=False
            for dr,dc in dirs:
                nr,nc = r+dr, c+dc
                if 1<=nr<ROWS-1 and 1<=nc<COLS-1 and self.grid.get(nr,nc)==WALL:
                    mr,mc = r+dr//2, c+dc//2
                    self.grid.set(mr,mc,EMPTY); self.draw_cell(mr,mc)
                    self.grid.set(nr,nc,EMPTY); self.draw_cell(nr,nc)
                    self._stack.append((nr,nc))
                    carved=True
                    break
            if not carved: self._stack.pop()
            steps-=1

        if self._stack:
            self.root.after(0, self._maze_tick)
        else:
            self._place_entrance_exit()
            self.animating=False

    def _place_entrance_exit(self):
        border=[]
        for c in range(COLS):
            if self.grid.get(1,c)==EMPTY: border.append((0,c,1,c))
            if self.grid.get(ROWS-2,c)==EMPTY: border.append((ROWS-1,c,ROWS-2,c))
        for r in range(ROWS):
            if self.grid.get(r,1)==EMPTY: border.append((r,0,r,1))
            if self.grid.get(r,COLS-2)==EMPTY: border.append((r,COLS-1,r,COLS-2))
        if not border:
            c=random.randrange(1,COLS,2)
            self.grid.set(0,c,EMPTY); border=[(0,c,1,c)]

        er,ec,ir,ic = random.choice(border)
        self.grid.set(er,ec,EMPTY)

        # 가장 먼 외곽 출구 선택(BFS)
        dist={(ir,ic):0}; q=deque([(ir,ic)])
        while q:
            r,c=q.popleft()
            for nr,nc in self.grid.neighbors4(r,c):
                if self.grid.get(nr,nc)!=WALL and (nr,nc) not in dist:
                    dist[(nr,nc)]=dist[(r,c)]+1; q.append((nr,nc))

        def inner_of(br,bc):
            if br==0: return (1,bc)
            if br==ROWS-1: return (ROWS-2,bc)
            if bc==0: return (br,1)
            return (br,COLS-2)

        candidates=set()
        for c in range(COLS):
            if (1,c) in dist: candidates.add((0,c))
            if (ROWS-2,c) in dist: candidates.add((ROWS-1,c))
        for r in range(ROWS):
            if (r,1) in dist: candidates.add((r,0))
            if (r,COLS-2) in dist: candidates.add((r,COLS-1))
        candidates.discard((er,ec))

        if candidates:
            best=None; bestd=-1
            for br,bc in candidates:
                irr,icc = inner_of(br,bc)
                if (irr,icc) in dist and dist[(irr,icc)]>bestd:
                    bestd=dist[(irr,icc)]; best=(br,bc)
            gr,gc = best
            self.grid.set(gr,gc,EMPTY)
        else:
            gr,gc,_,_ = random.choice(border)
            self.grid.set(gr,gc,EMPTY)

        # 시작/목표/플레이어 배치
        self.grid.start=(er,ec); self.grid.goal=(gr,gc); self.grid.player=(er,ec)
        self.draw_all()
        self.grid.set(*self.grid.start, START); self.draw_cell(*self.grid.start)
        self.grid.set(*self.grid.goal,  GOAL);  self.draw_cell(*self.grid.goal)
        self.grid.set(*self.grid.player, PLAYER); self.draw_cell(*self.grid.player)
        self.move_count=0; self.start_time=None; self.set_status()

    # ---------- 기타 ----------
    def slower(self, _=None):
        self.steps_per_tick = max(1, self.steps_per_tick//2)
        self.set_status()
    def faster(self, _=None):
        self.steps_per_tick = min(2000, self.steps_per_tick*2)
        self.set_status()
    def clear(self, _=None):
        if self.animating: return
        self.stop_timer()
        self.grid.clear(); self.move_count=0; self.start_time=None
        self.draw_all(); self.set_status()

if __name__=="__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
