"""Dry-run sequence only; this does not connect to or program physical hardware."""
from dataclasses import dataclass
import math

@dataclass
class Inputs:
    bottle: bool = False
    start: bool = False
    stop_ok: bool = True
    enable_ok: bool = True
    overload: bool = False
    feedback: bool = False
    reset: bool = False

class FillingLine:
    def __init__(self, fill_s=2.0):
        if not math.isfinite(fill_s) or fill_s<=0: raise ValueError('positive finite fill time required')
        self.fill_s=fill_s;self.state='idle';self.elapsed=0.;self.bottles=0;self.previous_start=False;self.feedback_elapsed=0.

    def step(self, dt, inputs):
        if not math.isfinite(dt) or dt<0: raise ValueError('nonnegative finite time step required')
        healthy=inputs.stop_ok and inputs.enable_ok and not inputs.overload
        rising=inputs.start and not self.previous_start
        self.previous_start=inputs.start
        # Hardwired contacts remove output common independently of this logic.
        if not healthy:
            self.state='fault';self.elapsed=0.;self.feedback_elapsed=0.
        elif self.state=='fault':
            if inputs.reset and not inputs.start: self.state='idle'
        elif self.state=='idle':
            if rising: self.state='convey'
        elif self.state=='convey':
            if inputs.bottle:
                self.state='filling';self.elapsed=0.;self.feedback_elapsed=0.
        elif self.state=='filling':
            if not inputs.bottle:
                self.state='fault';self.elapsed=0.
            else:
                self.elapsed+=dt
                if self.elapsed>=self.fill_s:
                    self.state='clear';self.bottles+=1
        elif self.state=='clear':
            if not inputs.bottle: self.state='convey'
        motor=self.state in ('convey','clear') and healthy
        if motor and not inputs.feedback:
            self.feedback_elapsed+=dt
            if self.feedback_elapsed>0.5: self.state='fault';motor=False
        else: self.feedback_elapsed=0.
        return dict(state=self.state,Y1=motor,Y2=self.state=='filling' and healthy,Y3=self.state in ('convey','filling','clear') and healthy,bottles=self.bottles)


def demo():
    line=FillingLine()
    steps=[('start',0,Inputs(start=True,feedback=True)),('bottle arrives',.1,Inputs(bottle=True)),
           ('fill 1 s',1,Inputs(bottle=True)),('fill 2 s',1,Inputs(bottle=True,feedback=True)),
           ('bottle clears',.1,Inputs(feedback=True)),('overload trips',.1,Inputs(overload=True)),
           ('reset',.1,Inputs(reset=True)),('new start',0,Inputs(start=True,feedback=True))]
    return [dict(event=event,**line.step(dt,i)) for event,dt,i in steps]
