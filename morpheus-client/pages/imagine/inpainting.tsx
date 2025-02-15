import { NextPage } from "next";

import ImagineBase from "@/components/ImagineBase/ImagineBase";
import { useDiffusion } from "@/context/SDContext";
import { useImagine } from "@/context/ImagineContext";
import { useAnalytics } from "@/context/GoogleAnalyticsContext";

const Inpainting: NextPage = () => {
  const { prompt } = useDiffusion();
  const { img2imgFile, maskFile, generateImages } = useImagine();
  const { sendAnalyticsRecord } = useAnalytics();
  const isFormValid =
    prompt.value.length > 0 && img2imgFile !== null && maskFile !== null;

  const handleGenerate = async () => {
    generateImages("inpainting");
    sendAnalyticsRecord("generate_images", {
      prompt: prompt.value,
      model: "inpainting",
    });
  };

  return (
    <ImagineBase
      formValid={isFormValid}
      showImageInput={true}
      showMaskInput={true}
      handleGenerate={handleGenerate}
    />
  );
};

export default Inpainting;
