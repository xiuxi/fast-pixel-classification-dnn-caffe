# coding=utf-8
"""
Fast object recognition of road objects 
with a deep neural neural network.
You can preview results in real time in GUI,
generate video with results or save all frames as images.
Coloring scheme should be compatible with CityScapes dataset.

You just need to copy your own pretrained model and its description to ./models
and optionally provide path to caffe installation folder.

To run with GUI you need to install OpenCV for python with gui support.
https://stackoverflow.com/questions/36833661/installing-opencv-with-gui-on-ubuntu

If GUI is not necessary, 'pip install opencv-python' may be sufficient.

See __main__ for the settings.

Mikalai Drabovich (nick.drabovich@amd.com)
"""
from __future__ import print_function
import os
import sys
import time

#import cProfile

import numpy as np
import weave

#if necessary, use custom caffe build
sys.path.insert(0, '../hipCaffe/python/')
import caffe

import cv2

def id2bgr(im):
    """
    A fast conversion from object id to color.
    :param im: 2d array with shape (w,h) with recognized object IDs as pixel values
    :return: color_image: BGR image with colors corresponding to detected object.
    The BGR values are compatible with CityScapes dataset:
    github.com/mcordts/cityscapesScripts/blob/master/cityscapesscripts/helpers/labels.py
    """
    w, h = im.shape
    color_image = np.empty((w, h, 3), dtype=np.uint8)
    code = """
    unsigned char cityscape_object_colors[19][3] = {
    {128, 64,128},  // road
    {232, 244, 35}, // sidewalk
    { 70, 70, 70},  // building
    {156, 102,102}, // wall
    {190,153,153},  // fence
    {153,153,153},  // pole
    {30,170, 250},  // traffic light
    {0, 220,  220}, // traffic sign
    {35,142, 107},  // vegetation
    {152,251,152},  // terrain
    { 180, 130,70}, // sky
    {60, 20, 220},  // person
    {0,  0,  255},  // rider
    { 142,  0,0},   // car
    { 70,  0, 0},   // truck
    {  100, 60,0},  // bus
    {  100, 80,0},  // train
    {  230,  0,0},  // motorcycle
    {32, 11, 119}   // bicycle
    };

    int impos=0;
    int retpos=0;
    for(int j=0; j<Nim[0]; j++) {
        for (int i=0; i<Nim[1]; i++) {
            unsigned char d=im[impos++];
            color_image[retpos++] = cityscape_object_colors[d][0];
            color_image[retpos++] = cityscape_object_colors[d][1];
            color_image[retpos++] = cityscape_object_colors[d][2];
        }
    }
    """
    weave.inline(code, ["im", "color_image"])
    return color_image


def fast_mean_subtraction_bgr(im):
    """
    Fast mean subtraction
    :param im: input image
    :return: image with subtracted mean values of ImageNet dataset
    """
    code = """
    float mean_r = 123;
    float mean_g = 117;
    float mean_b = 104;
    int retpos=0;
    for(int j=0; j<Nim[0]; j++) {
        for (int i=0; i<Nim[1]; i++) {
            im[retpos++] -=  mean_b;
            im[retpos++] -=  mean_g;
            im[retpos++] -=  mean_r;
        }
    }
    """
    weave.inline(code, ["im"])
    return im


def feed_and_run(input_frame):
    """
    Format input data and run object recognition 
    :param input_frame: image data from file
    :return: forward_time, segmentation_result
    """
    start = time.time()
    input_frame = input_frame.transpose((2, 0, 1))
    print("Data transpose took {} ms.".format(round((time.time() - start) * 1000)))

    start = time.time()
    net.blobs['data'].data[...] = input_frame
    print("Data input took {} ms.".format(round((time.time() - start) * 1000)))

    start = time.time()
    net.forward()
    forward_time = round((time.time() - start) * 1000)
    print("Net.forward() took {} ms.".format(forward_time))

    start = time.time()

    if model_has_argmax:
        result_with_train_ids = net.blobs['recognized_object_ids'].data[0].astype(np.uint8)
        result_with_train_ids = np.squeeze(result_with_train_ids, axis=0)
    else:
        result_with_train_ids = net.blobs['score'].data[0].argmax(axis=0).astype(np.uint8)

    print("ArgMax took {} ms.".format(round((time.time() - start) * 1000)))

    start = time.time()
    segmentation_result = id2bgr(result_with_train_ids)
    print("Conversion from object class ID to color took {} ms.".format(round((time.time() - start) * 1000)))

    return forward_time, segmentation_result


if __name__ == "__main__":

    #------------------------ Change main parameters here ---------------
 
    createVideoFromResults = True
    video_results_dir = './video_results/'
    
    show_gui = True
    save_image_results = False
    image_results_dir = './image_results/'

    input_w = 2048
    input_h = 1024

    # # Models with argmax and without upsampling are faster

    model_description = '../hipCaffe/models/deploy_model_without_upsampling_without_argmax.prototxt'
    model_has_argmax = False
    model_weights = '../hipCaffe/models/weights.caffemodel'
 
    # # original model
    # # model_description = '../hipCaffe/models/deploy_model_with_upsampling_without_argmax.prototxt'
    # # model_has_argmax = False
    # # 
    # # improved 1
    # # odel_description = '../hipCaffe/models/deploy_model_with_upsampling_with_argmax.prototxt'
    # # model_has_argmax = True
    # # 
    # # improved 2
    # # model_description = '../hipCaffe/models/deploy_model_without_upsampling_without_argmax.prototxt'
    # # model_has_argmax = False
    # # 
    # # improved 3, should be the fastest
    # # model_description = '../hipCaffe/models/deploy_model_without_upsampling_with_argmax.prototxt'
    # # model_has_argmax = True
    # # model_weights = '../hipCaffe/models/weights.caffemodel'
    #--------------------------------------------------------------------

    os.system("./generate_image_list_for_demo.sh")
    image_list_file = open('./image_list_video.txt')

    if not os.path.exists(image_results_dir):
        os.makedirs(image_results_dir)

    input_images_for_demo = image_list_file.read().splitlines()
    image_list_file.close()

    writer = None
    if createVideoFromResults:
        if not os.path.exists(video_results_dir):
            os.makedirs(video_results_dir)
        fps = 30
        codec = 'mp4v'
        videoFileName = 'result_at_30fps.mkv'
        fourcc = cv2.cv.CV_FOURCC(*codec)
        writer = cv2.VideoWriter(video_results_dir + videoFileName, fourcc, fps, (input_w, input_h))

    # Cache first 100 images for fast access
    prefetchNumFiles = 28
    input_data = []
    input_data_uint8 = []
    if prefetchNumFiles > 0:
        print("Prefetching first %d image files" % prefetchNumFiles)
        start = time.time()
        num_prefetched = 0

        for file_path in input_images_for_demo:
            if num_prefetched > prefetchNumFiles:
                break
            frame = cv2.imread(file_path)
            input_data_uint8.append(frame)
            frame = np.array(frame, dtype=np.float32)
            frame_ready = fast_mean_subtraction_bgr(frame)
            input_data.append(frame_ready)
            print('\r' + "Prefetching files: %d%% " % (100 * num_prefetched / float(prefetchNumFiles)))
            sys.stdout.flush()
            num_prefetched += 1

        print("")
        print("Prefetch completed in {} seconds.".format(round((time.time() - start))))

    caffe.set_mode_gpu()
    caffe.set_device(0)
    net = caffe.Net(model_description, 1, weights=model_weights)


    result_out_upscaled = np.empty((input_h, input_w, 3), dtype=np.uint8)
    # transparency of the overlaid object segments
    alpha = 0.7
    blended_result = np.empty((input_h, input_w, 3), dtype=np.uint8)

    if show_gui:
        cv2.namedWindow("Demo")

    # profiler = cProfile.Profile()
    # profiler.enable()

   
    num_images_processed = 0    
    for image in input_images_for_demo:     # main loop

        initial_time = time.time()

        start = time.time()
        if num_images_processed < prefetchNumFiles:
            frame = input_data[num_images_processed]
            frame_uint8 = input_data_uint8[num_images_processed]
        else:
            frame_uint8 = cv2.imread(image)
            frame_32f = np.array(frame_uint8, dtype=np.float32)
            frame = fast_mean_subtraction_bgr(frame_32f)

        print("File read time: {} ms.".format(round((time.time() - start) * 1000)))

        core_forward_time, recognition_result = feed_and_run(frame)

        start = time.time()
        result_out_upscaled = cv2.resize(recognition_result, (input_w, input_h), interpolation=cv2.INTER_NEAREST)
        print("Resize time: {} ms.".format(round((time.time() - start) * 1000)))

        start = time.time()
        cv2.addWeighted(result_out_upscaled, alpha, frame_uint8, 1.0 - alpha, 0.0, blended_result)#, cv2.CV_8U)
        print("Overlay detection results: {} ms.".format(round((time.time() - start) * 1000)))

        start = time.time()
        cv2.putText(blended_result, str(int(core_forward_time)) + "ms.", (20, 950), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 255), 10)
        print("Text render time: {} ms.".format(round((time.time() - start) * 1000)))

        start = time.time()

	if show_gui:
            cv2.imshow("Demo", blended_result)

	if save_image_results:
	    cv2.imwrite(image_results_dir + os.path.basename(image), blended_result)

        print("cv2 output time: {} ms.".format(round((time.time() - start) * 1000)))

        if createVideoFromResults:
            start = time.time()
            writer.write(blended_result)
            print("Add frame to video file: {} ms.".format(round((time.time() - start) * 1000)))

        key = cv2.waitKey(2)
        if key == 27:  # exit on ESC
            break

        num_images_processed += 1

        print("Total time with data i/o and image pre/post postprocessing - {} ms.".format(
            round((time.time() - initial_time) * 1000)))
        print("---------> Finished processing image #{}, {}, net.forward() time: {} ms.".format(num_images_processed,
                                                                                         os.path.basename(image),
                                                                                         core_forward_time))

    if createVideoFromResults:
        writer.release()

    if show_gui:
        cv2.destroyWindow("Demo")


    # profiler.disable()
    # print('\n\n\nProfiling results:')
    # profiler.print_stats(sort='time')
