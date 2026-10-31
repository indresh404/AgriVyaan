import React from 'react';
import { useProjectStore } from '../store/useProjectStore';
import { Step1Location } from './Step1Location';
import { Step2Field } from './Step2Field';
import { Step3Crop } from './Step3Crop';
import { Step4Camera } from './Step4Camera';
import { Step5Hotspots } from './Step5Hotspots';
import { Step6Drones } from './Step6Drones';
import { Step7Path } from './Step7Path';
import { Step8Review } from './Step8Review';
import { ChevronLeft, ChevronRight, Sliders, Shield } from 'lucide-react';

const STEP_TITLES = [
  'Location',
  'Field Geometry',
  'Crop Profile',
  'Camera & Optics',
  'Hotspots',
  'Fleet & Battery',
  'Path & Energy',
  'Review & Launch',
];

export const Wizard: React.FC = () => {
  const { wizardStep, setWizardStep } = useProjectStore();

  const renderStep = () => {
    switch (wizardStep) {
      case 1:
        return <Step1Location />;
      case 2:
        return <Step2Field />;
      case 3:
        return <Step3Crop />;
      case 4:
        return <Step4Camera />;
      case 5:
        return <Step5Hotspots />;
      case 6:
        return <Step6Drones />;
      case 7:
        return <Step7Path />;
      case 8:
        return <Step8Review />;
      default:
        return <Step1Location />;
    }
  };

  return (
    <div className="w-[430px] flex-shrink-0 h-full bg-slate-950/95 border-r border-slate-800 flex flex-col z-20 backdrop-blur-md">
      {/* Header */}
      <div className="p-4 border-b border-slate-800">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-sky-400 animate-pulse" />
            <h2 className="text-sm font-bold text-white uppercase tracking-wider">Mission Setup Wizard</h2>
          </div>
          <span className="text-[11px] font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded">
            Step {wizardStep} of 8
          </span>
        </div>

        {/* Step Progress Bar */}
        <div className="grid grid-cols-8 gap-1 mt-3">
          {STEP_TITLES.map((title, idx) => {
            const stepNum = idx + 1;
            const isCompleted = stepNum < wizardStep;
            const isCurrent = stepNum === wizardStep;
            return (
              <button
                key={title}
                onClick={() => setWizardStep(stepNum)}
                className={`h-1.5 rounded-full transition-all ${
                  isCurrent
                    ? 'bg-sky-400 ring-2 ring-sky-500/50'
                    : isCompleted
                    ? 'bg-emerald-500'
                    : 'bg-slate-800'
                }`}
                title={`${stepNum}. ${title}`}
              />
            );
          })}
        </div>
        <div className="text-[11px] font-medium text-slate-300 mt-2 truncate">
          {wizardStep}. {STEP_TITLES[wizardStep - 1]}
        </div>
      </div>

      {/* Step Content */}
      <div className="flex-1 overflow-y-auto p-4">{renderStep()}</div>

      {/* Footer Navigation */}
      <div className="p-4 border-t border-slate-800 flex items-center justify-between bg-slate-950">
        <button
          onClick={() => setWizardStep(wizardStep - 1)}
          disabled={wizardStep === 1}
          className="px-3 py-1.5 rounded text-xs font-semibold text-slate-300 bg-slate-900 hover:bg-slate-800 disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1 transition"
        >
          <ChevronLeft className="w-4 h-4" />
          Back
        </button>

        <span className="text-[10px] text-slate-500 uppercase tracking-wider font-semibold">
          AgriVyaan Studio v1.0
        </span>

        {wizardStep < 8 ? (
          <button
            onClick={() => setWizardStep(wizardStep + 1)}
            className="px-4 py-1.5 rounded text-xs font-bold text-white bg-sky-600 hover:bg-sky-500 flex items-center gap-1 transition shadow-md shadow-sky-950"
          >
            Next
            <ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <div className="w-16" />
        )}
      </div>
    </div>
  );
};
